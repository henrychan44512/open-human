"""FastAPI + SSE。前端是原生 HTML/CSS/JS，没有构建步骤。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__, paths
from ..config import Backend, config_path, load_config
from ..pack import PackError
from ..tools import Tools, scope_for
from .state import Runtime

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Open Human", docs_url=None, redoc_url=None)
app.mount("/s", StaticFiles(directory=STATIC), name="static")

_rt: Runtime | None = None


def runtime() -> Runtime:
    global _rt
    if _rt is None:
        _rt = Runtime(load_config())
    return _rt


# ---------- 页面 ----------


def _page(name: str) -> FileResponse:
    return FileResponse(STATIC / name, media_type="text/html; charset=utf-8")


@app.get("/")
def index() -> FileResponse:
    return _page("index.html")


@app.get("/chat/{slug}")
def chat_page(slug: str) -> FileResponse:
    return _page("chat.html")


@app.get("/settings")
def settings_page() -> FileResponse:
    return _page("settings.html")


# ---------- API ----------


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/humans")
def humans() -> dict:
    rt = runtime()
    out = []
    for slug in rt.slugs():
        try:
            loaded = rt.load(slug)
        except (PackError, OSError):
            continue
        meta = loaded.pack.meta
        out.append(
            {
                "slug": slug,
                "name": meta.name,
                "presence": str(meta.presence),
                "line": meta.first_line,
                "last_record": meta.last_record.isoformat() if meta.last_record else None,
                "memories": len(loaded.pack.memories),
                "online": False,
            }
        )
    online = rt.online()
    for item in out:
        item["online"] = online
    return {"humans": out, "online": online, "model": rt.config.llama.model}


@app.get("/api/humans/{slug}")
def human(slug: str) -> dict:
    rt = runtime()
    try:
        loaded = rt.load(slug)
    except PackError as exc:
        raise HTTPException(404, str(exc)) from exc
    meta = loaded.pack.meta
    return {
        "slug": slug,
        "name": meta.name,
        "presence": str(meta.presence),
        "first_line": meta.first_line,
        "sleep_line": meta.sleep_line,
        "wake_line": meta.wake_line,
        "idle_line": meta.idle_line,
        "memories": len(loaded.pack.memories),
        "indexed": len(loaded.index),
        "warnings": loaded.pack.warnings,
        "online": rt.online(),
    }


@app.get("/api/humans/{slug}/cards/{card_id}")
def card(slug: str, card_id: str) -> dict:
    rt = runtime()
    try:
        loaded = rt.load(slug)
    except PackError as exc:
        raise HTTPException(404, str(exc)) from exc
    for item in loaded.pack.memories:
        if item.id == card_id:
            # 只发抽屉真的会画的那几样。type / source / emotion 不上屏，就别过网络。
            return {
                "id": item.id,
                "date": item.date.isoformat(),
                "title": item.title,
                "people": item.people,
                "places": item.places,
                "tags": item.tags,
                "body": item.body,
            }
    raise HTTPException(404, f"没有这张卡: {card_id}")


@app.post("/api/warm/{slug}")
def warm(slug: str) -> dict:
    """等他醒，再把 persona 灌进前缀缓存。

    冷启动时这个请求会**真的挂住**到模型就绪为止 —— 页面上的进度条就挂在这里。
    """
    cost = runtime().warm(slug)
    return {"ok": cost >= 0, "seconds": round(max(cost, 0.0), 2)}


# ---------- 对话 ----------


class ChatIn(BaseModel):
    text: str
    tools: bool = False
    allow_mutating: bool = False


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _card_refs(cards) -> dict:
    """界面上要显示的是「哪一年 · 什么事」，不是卡 id。"""
    return {
        c.id: {"title": c.title, "date": c.date.isoformat(), "year": c.date.year}
        for c in cards
    }


def _stream(slug: str, text: str, use_tools: bool = False, allow_mutating: bool = False):
    rt = runtime()
    entry = rt.entry(slug)
    pending: list[dict] = []
    engine = entry.engine

    try:
        cards, plan = engine.prepare(text)
        yield _sse(
            "meta",
            {
                "citations": [c.id for c in cards],
                "cards": _card_refs(cards),
                "plan": plan.summary(),
                "tools": use_tools,
            },
        )
        with entry.lock:
            # 工具挂在引擎上，必须在锁里换：两个页面同时聊，谁后到谁说了算，
            # 但不能一个在跑的时候另一个把 tools 抽走。
            if use_tools:
                engine.tools = Tools(
                    scope_for(engine.pack.root),
                    confirm=lambda spec, args: allow_mutating,
                )
                engine.on_event = pending.append
            else:
                engine.tools = None
                engine.on_event = None

            for chunk in engine.respond(text, cards=cards):
                while pending:
                    yield _sse("tool", pending.pop(0))
                if chunk:
                    yield _sse("delta", {"text": chunk})
            while pending:
                yield _sse("tool", pending.pop(0))

            engine.tools = None
            engine.on_event = None
        last = engine.last
        stats = last.stats if last else None
        yield _sse(
            "done",
            {
                "text": last.reply if last else "",
                "citations": last.citations if last else [],
                "tools": last.tools if last else [],
                "ttft": round(stats.ttft_s, 3) if stats and stats.ttft_s else None,
                "tokens": stats.completion_tokens if stats else 0,
                "session": engine.session.path.name if engine.session.path else "",
            },
        )
    except Exception as exc:  # noqa: BLE001 — 任何失败都要让前端知道
        yield _sse("error", {"message": str(exc)})


@app.post("/api/chat/{slug}")
def chat(slug: str, body: ChatIn) -> StreamingResponse:
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "空消息")
    return StreamingResponse(
        _stream(slug, text, body.tools, body.allow_mutating),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/session/{slug}")
def session_state(slug: str) -> dict:
    """当前会话的对话记录。刷新页面靠它把记录画回来。

    没有引擎就返回空的，不新建 —— GET 不该有副作用。
    """
    entry = runtime().existing(slug)
    if entry is None:
        return {"name": "", "messages": [], "cards": {}}
    session = entry.engine.session
    cited = {cid for event in session.events for cid in event.citations}
    known = {m.id: m for m in entry.engine.pack.memories}
    return {
        "name": session.path.stem if session.path else "",
        "cards": _card_refs([known[cid] for cid in cited if cid in known]),
        "messages": [
            {"role": e.role, "text": e.content, "citations": e.citations, "ts": e.ts}
            for e in session.dialogue()
        ],
    }


@app.post("/api/session/{slug}/new")
def new_session(slug: str) -> dict:
    runtime().restart_session(slug)
    return {"ok": True}


# ---------- 设置 ----------


def _fmt(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _set_toml(text: str, section: str, key: str, value: object) -> str:
    """只改一行，保留注释和其它内容。"""
    lines = text.splitlines()
    header = f"[{section}]"
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        lines += ["", header, f"{key} = {_fmt(value)}"]
        return "\n".join(lines) + "\n"

    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")),
        len(lines),
    )
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for i in range(start + 1, end):
        if pattern.match(lines[i]):
            lines[i] = f"{key} = {_fmt(value)}"
            return "\n".join(lines) + "\n"
    lines.insert(start + 1, f"{key} = {_fmt(value)}")
    return "\n".join(lines) + "\n"


@app.get("/api/settings")
def get_settings() -> dict:
    cfg = runtime().config
    return {
        "version": __version__,
        "backend": cfg.app.default_model,
        "max_reply_tokens": cfg.app.max_reply_tokens,
        # key 一律不出这个进程，哪怕本地后端那个通常是空的
        "llama": cfg.llama.model_dump(exclude={"api_key"}),
        "deepseek": cfg.deepseek.model_dump(exclude={"api_key"}),
        "has_deepseek_key": bool(cfg.deepseek.api_key),
        "online": runtime().online(),
    }


class SettingsIn(BaseModel):
    backend: Backend | None = None
    max_reply_tokens: int | None = None
    llama_model: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    top_p: float | None = None


@app.post("/api/settings")
def post_settings(body: SettingsIn) -> dict:
    path = config_path()
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not text and (paths.root() / "config.example.toml").is_file():
        text = (paths.root() / "config.example.toml").read_text(encoding="utf-8")

    if body.backend:
        text = _set_toml(text, "app", "default_model", body.backend)
    if body.max_reply_tokens:
        text = _set_toml(text, "app", "max_reply_tokens", body.max_reply_tokens)
    if body.llama_model:
        text = _set_toml(text, "llama", "model", body.llama_model)
    if body.base_url:
        text = _set_toml(text, "llama", "base_url", body.base_url)
    if body.temperature is not None:
        text = _set_toml(text, "llama", "temperature", round(body.temperature, 2))
    if body.top_p is not None:
        text = _set_toml(text, "llama", "top_p", round(body.top_p, 2))

    path.write_text(text, encoding="utf-8")
    runtime().config = load_config(path)
    runtime().invalidate()
    return {"ok": True}
