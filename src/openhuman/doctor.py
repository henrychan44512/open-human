"""环境自检。oh doctor 的全部逻辑都在这里。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from . import localmodel, paths, tokens
from .config import Config, config_path, load_config
from .llm import LLMClient
from .pack import PackError, load_pack
from .pack.persona import PERSONA_BUDGET, compile_persona

Level = Literal["ok", "warn", "fail"]


@dataclass
class Check:
    level: Level
    name: str
    detail: str = ""


def check_python() -> list[Check]:
    if sys.version_info >= (3, 12):
        return [Check("ok", "Python", f"{sys.version.split()[0]}")]
    return [Check("fail", "Python", f"{sys.version.split()[0]}，需要 >= 3.12")]


def check_config() -> list[Check]:
    path = config_path()
    if path.is_file():
        return [Check("ok", "config.toml", str(path.relative_to(paths.root())))]
    example = paths.root() / "config.example.toml"
    if example.is_file():
        return [Check("warn", "config.toml", "还没创建，正在用内置默认值（可 cp config.example.toml）")]
    return [Check("warn", "config.toml", "没有配置文件，全部用默认值")]


def check_packs(slug: str | None) -> tuple[list[Check], object | None]:
    checks: list[Check] = []
    base = paths.humans_dir()
    if not base.is_dir():
        return [Check("fail", "humans/", f"目录不存在: {base}")], None

    slugs = paths.list_packs()
    if not slugs:
        return [Check("fail", "人格包", f"{base} 下没有找到人格包（human_data.md 或多文件形态）")], None
    checks.append(Check("ok", "人格包", f"{len(slugs)} 个: {', '.join(slugs)}"))

    target = slug or ("demo" if "demo" in slugs else slugs[0])
    if target not in slugs:
        checks.append(Check("fail", "选择的人格包", f"{target} 不存在"))
        return checks, None

    try:
        pack = load_pack(paths.pack_dir(target))
    except PackError as exc:
        checks.append(Check("fail", f"加载 {target}", str(exc)))
        return checks, None

    checks.append(
        Check("ok", f"加载 {target}", f"{pack.name} / {pack.meta.presence} / {len(pack.memories)} 张卡")
    )

    for warning in pack.warnings:
        checks.append(Check("warn", "包内容", warning))

    missing_source = [m.id for m in pack.memories if not m.retrievable]
    if missing_source:
        checks.append(Check("warn", "缺 source", f"{len(missing_source)} 张卡不进检索"))

    return checks, pack


def check_persona(pack, cfg: Config, base_url: str | None) -> list[Check]:
    report = bool(pack)
    if not report:
        return []
    text = compile_persona(pack)
    n, exact = tokens.count(text, base_url)
    how = "" if exact else "（估算）"
    if n > PERSONA_BUDGET:
        return [Check("fail", "persona 长度", f"{n} tok{how} > 预算 {PERSONA_BUDGET}")]
    return [Check("ok", "persona 长度", f"{n} tok{how} / 预算 {PERSONA_BUDGET}")]


def check_model(cfg: Config) -> list[Check]:
    path = localmodel.model_path(cfg)
    if not path.is_file():
        return [Check("fail", "模型文件", f"找不到 {cfg.llama.model_file}")]
    size_gb = path.stat().st_size / 1024**3
    return [Check("ok", "模型文件", f"{cfg.llama.model_file} ({size_gb:.2f} GB)")]


def check_server(cfg: Config) -> tuple[list[Check], str | None]:
    client = LLMClient(
        cfg.llama.base_url,
        cfg.llama.model,
        api_key=cfg.llama.api_key,
        local=True,
    )
    if not client.health():
        return [
            Check(
                "fail",
                "llama-server",
                f"{cfg.llama.base_url} 无响应。双击 Open Human.cmd 会自动拉起，或 oh serve",
            )
        ], None

    props = client.props()
    alias = props.get("model_alias") or "?"
    n_ctx = (props.get("default_generation_settings") or {}).get("n_ctx", 0)
    checks = [Check("ok", "llama-server", f"{cfg.llama.base_url} · {alias} · n_ctx={n_ctx}")]
    if n_ctx and n_ctx != cfg.llama.context:
        checks.append(
            Check("warn", "context 不一致", f"服务端 {n_ctx}，配置 {cfg.llama.context}")
        )
    return checks, cfg.llama.base_url


def check_data() -> list[Check]:
    folder = paths.sessions_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return [Check("fail", "data/sessions", f"不可写: {exc}")]
    count = len(list(folder.rglob("*.jsonl")))
    return [Check("ok", "data/sessions", f"可写，已有 {count} 个会话")]


def run(slug: str | None = None) -> list[Check]:
    cfg = load_config()
    checks: list[Check] = []
    checks += check_python()
    checks += check_config()

    pack_checks, pack = check_packs(slug)
    checks += pack_checks

    checks += check_model(cfg)

    server_checks, base_url = check_server(cfg)
    checks += server_checks

    if pack is not None:
        checks += check_persona(pack, cfg, base_url)

    checks += check_data()
    return checks


def failed(checks: list[Check]) -> bool:
    return any(c.level == "fail" for c in checks)
