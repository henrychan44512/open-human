"""命令行入口：oh serve / oh chat / oh replay / oh doctor / oh eval / oh packs。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__, doctor, localmodel, paths
from .chat import Engine, Session
from .config import Backend, load_config, make_client
from .eval import check_answer, load_cases, run_retrieval, summarize
from .llm import LLMClient, LLMError
from .memory import build as build_index
from .memory import plan as plan_query
from .pack import PackError, load_pack
from .tools import ToolSpec, Tools, scope_for

app = typer.Typer(add_completion=False, help="打开一个人格文件夹，AI 以第一人称成为他。")
console = Console()

LEVEL_STYLE = {"ok": ("✓", "green"), "warn": ("!", "yellow"), "fail": ("✗", "red")}

# serve 发现已经有实例在跑时用这个退出码：启动脚本见到它就直接退，不 pause。
ALREADY_RUNNING = 7


def _tame_streams() -> None:
    """让输出不至于把命令自己弄崩。

    中文 Windows 的 cp936 控制台编不出 `✓`（U+2713），`oh doctor > log.txt` 这种
    重定向更糟：stdout 是 GBK 且 errors 是 strict，rich 打印表格时直接抛
    UnicodeEncodeError —— 排障命令自己先崩了，日志里只剩一段 traceback。

    重定向出去的一律按 UTF-8 写（文件本来就该是 UTF-8）；终端上只把编码错误改成
    替换符，**不换编码** —— 换了中文就变乱码。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass  # 被别的库接管的流（pytest、rich 的 capture）不归我们动


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", "-V", help="显示版本后退出", is_eager=True)
    ] = False,
) -> None:
    """打开一个人格文件夹，AI 以第一人称成为他。"""
    _tame_streams()
    if version:
        console.print(
            f"[bold]open human[/] {__version__} · beta [dim]· 本地 MiniCPM5-2B Q4_K_M · CPU[/]"
        )
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        # 只敲 `oh` 的人多半不知道该干什么；给一份命令表，别静默退出
        console.print(ctx.get_help())
        raise typer.Exit()


def _client(backend: Backend | None) -> tuple[LLMClient, str]:
    cfg = load_config()
    try:
        client = make_client(cfg, backend)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    return client, client.model


@app.command(name="doctor")
def doctor_cmd(
    slug: Annotated[str | None, typer.Argument(help="检查哪个人格包")] = None,
) -> None:
    """检查环境：Python、配置、人格包、模型、llama-server。"""
    checks = doctor.run(slug)
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(width=2)
    table.add_column(style="bold", width=16)
    table.add_column()
    for check in checks:
        mark, style = LEVEL_STYLE[check.level]
        table.add_row(f"[{style}]{mark}[/]", check.name, check.detail)
    console.print(table)

    if doctor.failed(checks):
        console.print("\n[red]有项目没通过。[/] 先按上面的提示处理。")
        raise typer.Exit(1)
    console.print("\n[green]都通过。[/] 可以 `oh chat demo` 了。")


@app.command()
def packs() -> None:
    """列出可用的人格包。"""
    slugs = paths.list_packs()
    if not slugs:
        console.print("[yellow]humans/ 下没有可用的人格包。[/]")
        raise typer.Exit(1)
    for slug in slugs:
        try:
            pack = load_pack(paths.pack_dir(slug))
        except PackError as exc:
            console.print(f"  [red]✗[/] {slug}  {exc}")
            continue
        console.print(f"  [green]✓[/] {slug}  {pack.name}  ·  {len(pack.memories)} 张卡")


def _short(value: object, limit: int = 40) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _preview(spec: ToolSpec, args: dict) -> str:
    name = spec.name
    if name == "write_file":
        return f"整个覆盖 {args.get('path')}（{len(str(args.get('content', '')))} 字）"
    if name == "append_file":
        return f"在 {args.get('path')} 末尾加一句（{len(str(args.get('content', '')))} 字）"
    if name == "edit_file":
        return f"改 {args.get('path')}：「{_short(args.get('old'))}」→「{_short(args.get('new'))}」"
    if name == "run_command":
        return f"执行命令：{_short(args.get('cmd'), 80)}"
    return f"执行 {name}"


def _cli_confirm(spec: ToolSpec, args: dict) -> bool:
    console.print(f"\n[yellow]◇ 他要动手了[/]  {_preview(spec, args)}")
    try:
        raw = console.input("[yellow]  允许吗？[/] [dim](y/N)[/] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("[dim]  那就不做。[/]")
        return False
    return raw in ("y", "yes", "是", "好", "可以")


def _tool_line(event: dict) -> None:
    mark = "[green]✓[/]" if event.get("ok") else "[red]✗[/]"
    body = _short(event.get("output"), 70)
    console.print(f"[dim]{mark} {event.get('name')} · {body}[/]")


def make_tools(pack) -> Tools:
    return Tools(scope_for(pack.root), confirm=_cli_confirm)


def _talk(engine: Engine, stats: bool) -> int:
    """一问一答，直到他说结束。返回聊了几轮。"""
    rounds = 0
    while True:
        try:
            text = console.input("[bold cyan]你 › [/]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]（结束）[/]")
            return rounds
        if not text:
            continue
        if text in ("/exit", "/quit", ":q"):
            return rounds

        rounds += 1
        try:
            for chunk in engine.respond(text):
                console.print(chunk, end="", highlight=False, soft_wrap=True)
        except LLMError as exc:
            console.print(f"\n[red]{exc}[/]")
            continue
        console.print()

        last = engine.last
        if last and last.citations:
            console.print(f"[dim]  本次参考: {' · '.join(last.citations)}[/]")
        if stats and last:
            s = last.stats
            bits = []
            if s.ttft_s is not None:
                bits.append(f"首字 {s.ttft_s:.2f}s")
            if s.extra.get("decode_tps"):
                bits.append(f"{s.extra['decode_tps']} tok/s")
            bits.append(f"{s.completion_tokens} tok")
            if s.cached_tokens:
                bits.append(f"缓存 {s.cached_tokens}")
            console.print(f"[dim]  {' · '.join(bits)}[/]\n")


@app.command()
def chat(
    slug: Annotated[str, typer.Argument(help="人格包 slug")],
    model: Annotated[str | None, typer.Option("--model", "-m", help="llama | deepseek")] = None,
    no_warmup: Annotated[bool, typer.Option("--no-warmup", help="跳过开机预热")] = False,
    stats: Annotated[bool, typer.Option("--stats/--no-stats", help="显示每轮用量")] = True,
    resume: Annotated[bool, typer.Option("--resume", help="接着最近一次会话聊")] = False,
    tools: Annotated[bool, typer.Option("--tools", help="允许他用工具读写 workspace/")] = False,
) -> None:
    """和第一个人格包对话。"""
    try:
        pack = load_pack(paths.pack_dir(slug))
    except PackError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    backend: Backend = "llama" if model in (None, "llama") else "deepseek"
    if model not in (None, "llama", "deepseek"):
        console.print(f"[red]不认识的 --model {model!r}，只有 llama / deepseek[/]")
        raise typer.Exit(2)

    client, label = _client(backend)
    local = None
    if backend == "llama" and not client.health():
        # 和 oh serve 一个规矩：模型没开就替他开。没人该去背那一长串 llama-server 参数
        local = localmodel.ensure(
            load_config(), out=lambda line: console.print(f"[dim]{line}[/]")
        )
        if not client.health():
            console.print(
                f"[red]llama-server 没起来（{client.base_url}）。[/] 原因在 data/llama.log。"
            )
            raise typer.Exit(1)

    session = _open_session(slug, resume)
    index = build_index(pack)
    toolset = make_tools(pack) if tools else None
    engine = Engine(
        pack, client, session, index=index, tools=toolset,
        on_event=_tool_line if toolset else None,
    )

    console.print(
        Panel(
            f"[bold]{pack.name}[/]  [dim]{label} · {session.path.name if session.path else '内存'}"
            f" · {len(index)} 张卡可检索"
            + (f" · {len(toolset)} 个工具" if toolset else "")
            + "[/]",
            border_style="bright_black",
            padding=(0, 1),
        )
    )

    if not no_warmup and backend == "llama":
        with console.status("[dim]正在唤醒…[/]", spinner="dots"):
            cost = engine.warmup()
        console.print(f"[dim]预热 {cost:.1f}s[/]")

    console.print(f"[italic]{engine.greeting()}[/]\n")

    try:
        rounds = _talk(engine, stats)
    finally:
        localmodel.stop(local)
    console.print(f"[dim]{rounds} 轮，会话存在 {session.path}[/]")


def _open_session(slug: str, resume: bool) -> Session:
    return Session.resume(slug) if resume else Session.create(slug)


@app.command()
def replay(
    target: Annotated[str, typer.Argument(help="slug（取最近一次会话）或 .jsonl 路径")],
) -> None:
    """回放一次会话。"""
    path = Path(target)
    if not path.is_file():
        found = paths.latest_session(target)
        if found is None:
            console.print(f"[red]找不到会话: {target}[/]")
            raise typer.Exit(1)
        path = found

    session = Session.load(path)
    console.print(f"[dim]{path}[/]  {len(session)} 条事件\n")
    console.print(session.replay())


def _listening(host: str, port: int) -> bool:
    """端口上是不是已经有个 open human 在应答（双击两次不该起两个）。"""
    import socket
    import urllib.error
    import urllib.request

    probe = "127.0.0.1" if host in ("0.0.0.0", "") else host
    try:
        with socket.create_connection((probe, port), timeout=0.6):
            pass
    except OSError:
        return False
    try:
        with urllib.request.urlopen(f"http://{probe}:{port}/health", timeout=1.5) as res:
            return res.status == 200
    except (OSError, urllib.error.URLError):
        return False


def landing(url: str) -> str:
    """双击之后该直接看见谁。

    只有一个人格包时，中间那层「点一下他」的菜单是多余的：窗口开出来就该是他。
    多人格才需要列表页来做选择。
    """
    slugs = paths.list_packs()
    return f"{url}/chat/{slugs[0]}" if len(slugs) == 1 else url


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="监听地址；手机访问用 0.0.0.0")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p")] = 8710,
    browser: Annotated[bool, typer.Option("--open/--no-open", help="自动打开界面")] = True,
    model: Annotated[bool, typer.Option("--model/--no-model", help="自动拉起本地模型")] = True,
    as_window: Annotated[
        bool, typer.Option("--window/--browser", help="开应用窗口，还是普通标签页")
    ] = True,
) -> None:
    """启动 Web 界面。双击启动脚本跑的也是这条。"""
    import os
    import threading
    import time
    import webbrowser

    import uvicorn

    from .server.app import app as web
    from .window import SHELL_ENV, open_window, publish

    cfg = load_config()
    probe = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = f"http://{probe}:{port}"

    def show() -> None:
        page = landing(url)
        if os.environ.get(SHELL_ENV):
            # 壳里跑的时候，窗口交给 cmd.exe 开：从 python 里拉浏览器，
            # 这台机器上会被拦（拉起一两秒就没了），见 BUILD.md §14。
            publish(page)
            return
        try:
            if as_window and open_window(page):
                return
        except Exception:  # noqa: BLE001 — 开窗崩了也得退回标签页，不能什么都不弹
            pass
        webbrowser.open(page)

    def show_when_ready() -> None:
        """服务一应答就开窗，不等固定秒数 —— 早开一秒，就少一秒黑屏。

        没等到也照开：那至少让人看见浏览器的报错，而不是在背后干等。
        """
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not _listening(host, port):
            time.sleep(0.1)
        show()

    if _listening(host, port):
        console.print(f"[yellow]已经在跑了[/]  →  {landing(url)}")
        if browser:
            show()
        # 退出码 7 是给启动脚本看的：第二次双击只是把窗口叫回来，
        # 不该再留下一个等你按任意键的黑窗口。
        raise typer.Exit(ALREADY_RUNNING)

    # 模型放后台起。窗口不该为它等 5 秒 —— 那 5 秒现在写在页面上，
    # 是「正在把他叫醒」，而不是一个不说话的黑窗口。
    child: dict[str, object] = {"proc": None}
    if model and cfg.app.default_model == "llama":

        def bring_up() -> None:
            child["proc"] = localmodel.ensure(
                cfg, out=lambda line: console.print(f"[dim]{line}[/]")
            )

        threading.Thread(target=bring_up, name="model", daemon=True).start()

    console.print(f"[dim]open human[/]  →  [bold]{landing(url)}[/]")
    console.print("[dim]Ctrl+C 结束[/]")

    if browser:
        threading.Thread(target=show_when_ready, name="window", daemon=True).start()

    try:
        uvicorn.run(web, host=host, port=port, log_level="warning")
    finally:
        localmodel.stop(child["proc"])


@app.command(name="eval")
def eval_cmd(
    slug: Annotated[str, typer.Argument(help="人格包 slug")] = "demo",
    k: Annotated[int, typer.Option("--k", help="top-k")] = 5,
    answers: Annotated[bool, typer.Option("--answers", help="真的让模型答一遍（慢）")] = False,
    cases_file: Annotated[str | None, typer.Option("--cases", help="题库路径")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="打印每道题的命中")] = False,
) -> None:
    """跑 30 题评测：检索命中率 + 引用正确性。"""
    try:
        pack = load_pack(paths.pack_dir(slug))
    except PackError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    index = build_index(pack)
    cases = load_cases(Path(cases_file) if cases_file else None)
    rows = run_retrieval(index, pack, cases, k=k)

    if verbose:
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("id", width=4)
        table.add_column("问题", width=30)
        table.add_column("命中")
        table.add_column("", width=2)
        for row in rows:
            mark = "[green]✓[/]" if row.ok else "[red]✗[/]"
            top = row.top[0] if row.top else "[dim]（无）[/]"
            table.add_row(row.case.id, row.case.q, top, mark)
        console.print(table)

    summary = summarize(rows)
    console.print(
        f"\n检索命中  [bold]{summary['hit']}/{summary['memory']}[/] "
        f"= {summary['hit_rate']:.0%}   "
        f"（目标 ≥ 80%）"
    )
    console.print(
        f"首选命中  [bold]{summary['top1']}/{summary['memory']}[/] "
        f"= {summary['top1_rate']:.0%}   [dim]（top-1 就是那张卡）[/]"
    )
    console.print(
        f"不该有命中  [bold]{summary['quiet']}/{summary['scope']}[/] "
        f"= {summary['quiet_rate']:.0%}"
    )

    bad = [r for r in rows if not r.ok]
    if bad and not verbose:
        for row in bad:
            mark = "[yellow]≈[/]" if row.case.known else "[red]✗[/]"
            note = "已知局限" if row.case.known else row.note
            console.print(
                f"  {mark} {row.case.id} {row.case.q} → {row.top or '（无）'} {note}"
            )

    failed = False
    if summary["hit_rate"] < 0.8:
        console.print("[red]检索命中率不达标。[/]")
        failed = True
    if summary["quiet_rate"] < 0.8:
        console.print("[red]资料外的问题命中太多了 —— 那就是在编。[/]")
        failed = True

    if answers:
        client, _ = _client(None)
        if not client.health():
            console.print("[red]llama-server 没起来，跳过回答检查。[/]")
            raise typer.Exit(1)
        violations = 0
        console.print("\n[dim]正在让模型逐题回答…[/]")
        for case in [r.case for r in rows if r.case.kind == "memory"]:
            hits = index.search(plan_query(case.q, pack))
            cards = [h.card for h in hits]
            engine = Engine(pack, client, Session(slug, None), index=None)
            reply = "".join(engine.respond(case.q, cards=cards))
            bad_facts = check_answer(reply, cards)
            if bad_facts:
                violations += 1
                console.print(f"  [yellow]![/] {case.id} 引用了卡里没有的: {bad_facts}")
        console.print(
            f"引用检查  [bold]{len([c for c in cases if c.kind == 'memory']) - violations}"
            f"/{len([c for c in cases if c.kind == 'memory'])}[/] 无编造"
        )
        if violations:
            failed = True

    if failed:
        raise typer.Exit(1)
    console.print("\n[green]通过。[/]")


if __name__ == "__main__":
    app()
