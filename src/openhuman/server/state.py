"""运行时状态：加载人格包、建索引、持有会话。

一个 slug 一个 Engine，会话在第一次聊天时创建并一直用到进程结束。
单用户桌面应用，不做多租户。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from .. import localmodel
from ..chat import Engine, Session
from ..config import Backend, Config, load_config, make_client
from ..llm import LLMClient
from ..memory import MemoryIndex, build
from ..pack import Pack, PackError, load_pack
from ..paths import list_packs, pack_dir

# 开机时窗口比模型先出来，页面上的进度条走的就是这一段。等这么久还不醒，
# 就当它起不来了，别让那句「正在把他叫醒」一直挂着。
BOOT_WAIT = 70.0


@dataclass
class Loaded:
    pack: Pack
    index: MemoryIndex


@dataclass
class Entry:
    engine: Engine
    warm_s: float | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class Runtime:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()
        self._packs: dict[str, Loaded] = {}
        self._engines: dict[str, Entry] = {}

    # ---------- 人格包 ----------

    def slugs(self) -> list[str]:
        return list_packs()

    def load(self, slug: str) -> Loaded:
        if slug not in self._packs:
            pack = load_pack(pack_dir(slug))
            self._packs[slug] = Loaded(pack=pack, index=build(pack))
        return self._packs[slug]

    def invalidate(self) -> None:
        """配置变了，人格包和引擎都要重建。

        会话不跟着丢 —— 只是改了个温度，人不该突然失忆。
        """
        sessions = {slug: entry.engine.session for slug, entry in self._engines.items()}
        self._packs.clear()
        self._engines.clear()
        for slug, session in sessions.items():
            try:
                loaded = self.load(slug)
            except (PackError, OSError):
                continue  # 包被删了/改坏了，就让它变成一个没有记忆的新会话
            self._engines[slug] = Entry(
                engine=Engine(loaded.pack, self.client(), session, index=loaded.index)
            )

    # ---------- 模型 ----------

    def client(self, backend: Backend | None = None) -> LLMClient:
        return make_client(self.config, backend)

    def online(self) -> bool:
        """云端没有 /health 可探，有 key 就算在线；本地要真的能推理。"""
        if self.config.app.default_model == "deepseek":
            return bool(self.config.deepseek.api_key)
        return self.client().health()

    def wait_online(self, timeout: float = BOOT_WAIT) -> bool:
        """等他醒。模型可能还在从磁盘往内存里搬。

        这不是「多等一会儿」的保险，而是开机路径的一部分：窗口先出来，
        `/api/warm` 挂在这儿，页面上的进度条走多久，他就醒得多慢。
        """
        if self.online():
            return True
        if localmodel.program(self.config) is None:
            return False  # 压根没装，等也等不来
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.3)
            if self.online():
                return True
        return False

    # ---------- 会话 ----------

    def entry(self, slug: str) -> Entry:
        if slug not in self._engines:
            loaded = self.load(slug)
            # 接着上次的会话：关掉再开，他还该记得昨天
            session = Session.resume(slug)
            engine = Engine(
                loaded.pack,
                self.client(),
                session,
                index=loaded.index,
            )
            self._engines[slug] = Entry(engine=engine)
        return self._engines[slug]

    def existing(self, slug: str) -> Entry | None:
        """只查不建：GET 之类的读请求不该顺手开一个新会话文件。"""
        return self._engines.get(slug)

    def warm(self, slug: str) -> float:
        """把他叫醒，再把 persona 前缀灌进 llama.cpp 缓存。醒不过来返回 -1。"""
        if self.config.app.default_model != "llama":
            return 0.0  # 云端没有前缀缓存要灌，别白花一次请求
        if not self.wait_online():
            return -1.0
        entry = self.entry(slug)
        with entry.lock:
            if entry.warm_s is None:
                try:
                    entry.warm_s = entry.engine.warmup()
                except Exception:
                    entry.warm_s = -1.0
            return entry.warm_s

    def restart_session(self, slug: str) -> None:
        """从头开始：开一个真的新会话。

        只把引擎丢掉是不够的 —— 下一次请求会 `Session.resume` 到最近那个文件，
        等于什么都没忘，界面上看就是「点了没反应」。
        """
        self._engines.pop(slug, None)
        try:
            loaded = self.load(slug)
        except (PackError, OSError):
            return
        self._engines[slug] = Entry(
            engine=Engine(
                loaded.pack, self.client(), Session.create(slug), index=loaded.index
            )
        )
