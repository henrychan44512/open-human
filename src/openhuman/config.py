"""配置：config.toml + 环境变量覆盖。

没有 config.toml 时用内置默认值，所以 `oh doctor` 在裸仓库里也能跑。
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from . import paths
from .llm import LLMClient

Backend = Literal["llama", "deepseek"]


class AppConfig(BaseModel):
    default_model: Backend = "llama"
    max_reply_tokens: int = 400


class LlamaConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8080"
    model: str = "MiniCPM5-2B"
    model_file: str = "models/MiniCPM5-2B-Q4_K_M.gguf"
    api_key: str = ""
    temperature: float = 0.75
    top_p: float = 0.9
    context: int = 8192


class DeepSeekConfig(BaseModel):
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    api_key: str = ""
    temperature: float = 0.95
    top_p: float = 0.95


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    llama: LlamaConfig = Field(default_factory=LlamaConfig)
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)


def config_path() -> Path:
    return paths.root() / "config.toml"


def load_config(path: Path | None = None) -> Config:
    target = path or config_path()
    raw: dict = {}
    if target.is_file():
        with target.open("rb") as fh:
            raw = tomllib.load(fh)

    cfg = Config.model_validate(raw)

    # 环境变量优先，避免把 key 写进文件
    if key := os.environ.get("DEEPSEEK_API_KEY"):
        cfg.deepseek.api_key = key
    if base := os.environ.get("LLAMA_BASE_URL"):
        cfg.llama.base_url = base
    # 选模型：启动脚本不碰 config.toml，只把这两个变量传进来。
    # 1B / 2B 只是两份权重，代码里没有分支。
    if model_file := os.environ.get("OH_MODEL_FILE"):
        cfg.llama.model_file = model_file
    if model_name := os.environ.get("OH_MODEL_NAME"):
        cfg.llama.model = model_name
    return cfg


def make_client(cfg: Config, backend: Backend | None = None) -> LLMClient:
    """按后端名造一个客户端。云端缺 key 抛 ValueError。"""
    name = backend or cfg.app.default_model
    if name == "deepseek":
        d = cfg.deepseek
        if not d.api_key:
            raise ValueError("没有 DEEPSEEK_API_KEY 环境变量")
        return LLMClient(
            d.base_url,
            d.model,
            api_key=d.api_key,
            temperature=d.temperature,
            top_p=d.top_p,
            max_tokens=cfg.app.max_reply_tokens,
            local=False,
        )
    lc = cfg.llama
    return LLMClient(
        lc.base_url,
        lc.model,
        api_key=lc.api_key,
        temperature=lc.temperature,
        top_p=lc.top_p,
        max_tokens=cfg.app.max_reply_tokens,
        local=True,
    )
