"""配置：环境变量覆盖。

启动脚本靠 `OH_MODEL_FILE` / `OH_MODEL_NAME` 在 1B 和 2B 之间切换，
所以这两个覆盖必须稳 —— 双击进去发现「模型明明在，它说找不到」是最难受的开局。
"""

from __future__ import annotations

from openhuman import config


def test_default_weights_are_the_2b_ones(monkeypatch):
    monkeypatch.delenv("OH_MODEL_FILE", raising=False)
    monkeypatch.delenv("OH_MODEL_NAME", raising=False)
    cfg = config.load_config()
    assert cfg.llama.model_file == "models/MiniCPM5-2B-Q4_K_M.gguf"
    assert cfg.llama.model == "MiniCPM5-2B"


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("OH_MODEL_FILE", "models/MiniCPM5-1B-Q4_K_M.gguf")
    monkeypatch.setenv("OH_MODEL_NAME", "MiniCPM5-1B")
    cfg = config.load_config()
    assert cfg.llama.model_file == "models/MiniCPM5-1B-Q4_K_M.gguf"
    assert cfg.llama.model == "MiniCPM5-1B"


def test_llama_base_url_env_override(monkeypatch):
    monkeypatch.setenv("LLAMA_BASE_URL", "http://127.0.0.1:9999")
    cfg = config.load_config()
    assert cfg.llama.base_url == "http://127.0.0.1:9999"
