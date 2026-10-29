"""连续多轮压测：打真模型，看会不会越聊越崩。

    .venv\\Scripts\\python.exe scripts\\stress_chat.py [轮数] [slug]

检查四件事：
1. 每一轮都能拿到 done 事件，没有 error；
2. 首字延迟和整轮耗时随轮数怎么变（历史在长，prefill 不能失控）；
3. 引用有没有串台；
4. 会话文件是不是照样一行一行写下去。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8710"

TURNS = [
    "你还记得第一次上讲台那天吗",
    "那天你穿的是什么衣服",
    "学生说你手在抖，你当时怎么回的",
    "后来呢",
    "发大水那年是怎么上课的",
    "走廊里冷不冷",
    "你父亲是哪年走的",
    "他走的时候你在哪儿",
    "儿子结婚那天你讲话了吗",
    "讲了几分钟",
    "念念出生的时候你在哪儿",
    "她小时候你带过她吗",
    "你哪年退休的",
    "退休那天怎么回的家",
    "你和老伴去黄山是几月",
    "她怎么上去的",
    "老伴做手术那天你在干嘛",
    "那阵子家里谁在做饭",
    "有学生来看过你吗",
    "阳台上养的是什么花",
]


def post(path: str, payload: dict, timeout: float = 300.0) -> str:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8")


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as res:
        return json.load(res)


def parse_sse(body: str) -> dict:
    """把 SSE 拆成 {'done': ..., 'meta': ..., 'tools': [], 'errors': []}。"""
    out: dict = {"done": None, "meta": None, "tools": [], "errors": []}
    for block in body.split("\n\n"):
        name, data = None, ""
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:].strip()
            elif line.startswith("data: "):
                data += line[6:]
        if not name or not data:
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if name in ("done", "meta"):
            out[name] = payload
        elif name == "tool":
            out["tools"].append(payload)
        elif name == "error":
            out["errors"].append(payload.get("message", ""))
    return out


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else len(TURNS)
    slug = sys.argv[2] if len(sys.argv) > 2 else "demo"

    post(f"/api/session/{slug}/new", {})
    print(f"{'#':>2}  {'首字':>5} {'整轮':>6} {'字数':>4}  引用")
    bad = 0
    slowest = 0.0
    start = time.perf_counter()

    for i in range(rounds):
        text = TURNS[i % len(TURNS)]
        sent = time.perf_counter()
        body = post(f"/api/chat/{slug}", {"text": text})
        took = time.perf_counter() - sent
        slowest = max(slowest, took)
        events = parse_sse(body)

        if events["errors"] or not events["done"]:
            bad += 1
            print(f"{i + 1:>2}  FAIL  {events['errors'] or '没有 done 事件'}")
            continue

        done = events["done"]
        meta = events["meta"] or {}
        ttft = done.get("ttft")
        print(
            f"{i + 1:>2}  {ttft if ttft is None else f'{ttft:.1f}s':>5} "
            f"{took:>5.1f}s {len(done.get('text', '')):>4}  "
            f"{' '.join(meta.get('citations') or []) or '-'}"
        )

    total = time.perf_counter() - start
    session = get(f"/api/session/{slug}")
    events = len(session.get("messages") or [])
    print(
        f"\n{rounds} 轮 · {total:.0f}s · 最慢一轮 {slowest:.1f}s · "
        f"失败 {bad} · 会话里 {events} 条消息"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
