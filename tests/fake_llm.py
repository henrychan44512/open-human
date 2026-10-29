"""不依赖真模型的假后端。

两种用法：
- `FakeClient`：对象级替身，给 engine / cli 测试用。
- `FakeServer`：真的起一个 HTTP 服务，说 OpenAI 兼容协议，
  用来测 LLMClient 的 SSE 解析和 think 剥离。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openhuman.llm.client import Stats


class FakeClient:
    """长得像 LLMClient，但只背台词。"""

    model = "fake-model"

    def __init__(
        self,
        replies: list[str] | str = "嗯。",
        *,
        chunk_size: int = 3,
        calls: list[list[dict]] | None = None,
    ) -> None:
        self.replies = [replies] if isinstance(replies, str) else list(replies)
        self.chunk_size = chunk_size
        # calls[i] 是第 i 轮要吐的工具调用，没写就是纯文本
        self.scripts = calls or []
        self.stats = Stats(model=self.model)
        self.tool_calls: list[dict] = []
        self.calls: list[list[dict]] = []
        self._idx = 0

    def stream(
        self,
        messages: list[dict],
        *,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> Iterator[str]:
        self.calls.append(messages)
        self.tools_seen = tools
        index = min(self._idx, len(self.replies) - 1)
        reply = self.replies[index]
        self._idx += 1

        self.tool_calls = list(self.scripts[index]) if index < len(self.scripts) else []
        self.stats = Stats(
            model=self.model,
            prompt_tokens=sum(len(m.get("content") or "") for m in messages),
            completion_tokens=len(reply),
            ttft_s=0.01,
        )
        for i in range(0, len(reply), self.chunk_size):
            yield reply[i : i + self.chunk_size]

    def complete(self, messages: list[dict], *, max_tokens: int | None = None) -> str:
        return "".join(self.stream(messages, max_tokens=max_tokens))

    @property
    def last_messages(self) -> list[dict]:
        return self.calls[-1] if self.calls else []


class FakeServer:
    """OpenAI 兼容的最小 HTTP 服务。"""

    def __init__(
        self,
        reply: str = "嗯，我记得。",
        *,
        prefix: str = "",
        usage: dict | None = None,
    ) -> None:
        self.reply = reply
        self.prefix = prefix
        self.usage = usage or {"prompt_tokens": 12, "completion_tokens": 5}
        self.requests: list[dict] = []
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ---------- 生命周期 ----------

    def __enter__(self) -> FakeServer:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args) -> None:  # 静音
                pass

            def do_GET(self) -> None:
                if self.path == "/health":
                    self._json({"status": "ok"})
                else:
                    self.send_error(404)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.requests.append(body)

                if self.path.endswith("/tokenize"):
                    self._json({"tokens": list(range(len(body.get("content", ""))))})
                    return
                if not self.path.endswith("/chat/completions"):
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                text = outer.prefix + outer.reply
                for i in range(0, len(text), 4):
                    chunk = text[i : i + 4]
                    event = {
                        "choices": [{"delta": {"content": chunk}, "finish_reason": None}]
                    }
                    self._sse(event)
                self._sse(
                    {
                        "choices": [{"delta": {}, "finish_reason": "stop"}],
                        "usage": outer.usage,
                    }
                )
                self._write(b"data: [DONE]\n\n")

            def _json(self, payload: dict) -> None:
                raw = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _sse(self, payload: dict) -> None:
                self._write(b"data: " + json.dumps(payload).encode() + b"\n\n")

            def _write(self, raw: bytes) -> None:
                try:
                    self.wfile.write(raw)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def base_url(self) -> str:
        assert self._httpd is not None
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"
