"""HTTP 层。

这里不要 `from .app import app` —— 那会把 `openhuman.server.app` 这个名字
占掉，包里的子模块就取不到了。要实例请写 `from openhuman.server.app import app`。
"""

__all__: list[str] = []
