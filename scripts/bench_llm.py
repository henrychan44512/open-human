"""Phase 0 benchmark: measure llama-server prefill / decode / TTFT.

Usage:
    .venv/Scripts/python.exe scripts/bench_llm.py --label 8192
    .venv/Scripts/python.exe scripts/bench_llm.py --label 8192 --json out.json

Talks to an already-running llama-server on 127.0.0.1:8080.
Uses /tokenize to hit exact prompt sizes, /completion for timings.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, asdict

import httpx

BASE = "http://127.0.0.1:8080"
MODEL = "MiniCPM5-2B"

FILLER = (
    "那年冬天特别冷，屋檐下挂了很长的冰凌。我每天早上五点起床，"
    "先把炉子点着，再烧一壶水。学校在城东，走过去要四十分钟，"
    "路上会经过一座石桥和一个菜市场。学生们大多住在附近的巷子里，"
    "有的家里开小卖部，有的父母在纺织厂上班。我教历史，也教地理，"
    "一个礼拜十八节课。下课以后我常常留在办公室批改作业，"
    "窗外的梧桐树影子一点一点挪到墙上。"
)


@dataclass
class Result:
    label: str
    target_tokens: int
    prompt_tokens: int
    prefill_tps: float
    decode_tps: float
    predicted_n: int
    prefill_ms: float
    decode_ms: float


def get(client: httpx.Client, path: str) -> dict:
    r = client.get(BASE + path, timeout=30)
    r.raise_for_status()
    return r.json()


def count_tokens(client: httpx.Client, text: str) -> int:
    r = client.post(BASE + "/tokenize", json={"content": text}, timeout=60)
    r.raise_for_status()
    return len(r.json()["tokens"])


def build_prompt(client: httpx.Client, target: int) -> str:
    """Grow FILLER until /tokenize reports >= target tokens."""
    base = FILLER
    n_base = count_tokens(client, base)
    if n_base <= 0:
        raise RuntimeError("tokenizer returned no tokens")
    copies = max(1, round(target / n_base))
    text = base * copies
    # trim in ~2% steps until we are at or just under target
    while count_tokens(client, text) > target and copies > 1:
        copies -= 1
        text = base * copies
    return text


def run_once(client: httpx.Client, prompt: str, n_predict: int) -> dict:
    body = {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": False,
        "cache_prompt": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    t0 = time.perf_counter()
    r = client.post(BASE + "/completion", json=body, timeout=600)
    r.raise_for_status()
    wall = time.perf_counter() - t0
    data = r.json()
    t = data.get("timings") or {}
    return {
        "wall_s": round(wall, 3),
        "prompt_n": t.get("prompt_n", 0),
        "prompt_ms": t.get("prompt_ms", 0.0),
        "prompt_per_second": t.get("prompt_per_second", 0.0),
        "predicted_n": t.get("predicted_n", 0),
        "predicted_ms": t.get("predicted_ms", 0.0),
        "predicted_per_second": t.get("predicted_per_second", 0.0),
    }


def measure_ttft(client: httpx.Client, prompt: str) -> float | None:
    """Seconds until the first content delta arrives (streaming)."""
    body = {
        "prompt": prompt,
        "n_predict": 64,
        "temperature": 0.7,
        "stream": True,
        "cache_prompt": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    t0 = time.perf_counter()
    first = None
    with client.stream("POST", BASE + "/completion", json=body, timeout=600) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                ev = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if ev.get("content"):
                first = time.perf_counter() - t0
                break
    return None if first is None else round(first, 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="default", help="config label, e.g. 8192")
    ap.add_argument("--json", default=None, help="write raw results here")
    ap.add_argument("--targets", default="512,1024,2048,3500")
    ap.add_argument("--n-predict", type=int, default=200)
    args = ap.parse_args()

    targets = [int(x) for x in args.targets.split(",")]
    client = httpx.Client(timeout=600)

    props = get(client, "/props")
    n_ctx = props.get("default_generation_settings", {}).get("n_ctx", 0)
    slots = props.get("total_slots", 0)
    print(f"server: {props.get('model_alias')}  build={props.get('build_info')}  n_ctx={n_ctx} slots={slots}")

    # warmup: page in weights, settle allocator
    warm = build_prompt(client, 256)
    run_once(client, warm, 8)
    print("warmup done\n")

    results: list[Result] = []
    ttft_samples: list[float] = []

    for target in targets:
        prompt = build_prompt(client, target)
        runs = [run_once(client, prompt, args.n_predict) for _ in range(3)]
        prefill = statistics.median(r["prompt_per_second"] for r in runs)
        decode = statistics.median(r["predicted_per_second"] for r in runs)
        res = Result(
            label=args.label,
            target_tokens=target,
            prompt_tokens=runs[0]["prompt_n"],
            prefill_tps=round(prefill, 1),
            decode_tps=round(decode, 1),
            predicted_n=runs[0]["predicted_n"],
            prefill_ms=round(runs[0]["prompt_ms"], 0),
            decode_ms=round(runs[0]["predicted_ms"], 0),
        )
        results.append(res)
        print(
            f"prompt {res.prompt_tokens:>5} tok | "
            f"prefill {res.prefill_tps:>7.1f} tok/s ({res.prefill_ms:>7.0f} ms) | "
            f"decode {res.decode_tps:>6.1f} tok/s ({res.decode_ms:>6.0f} ms) | "
            f"gen {res.predicted_n} tok"
        )

    # TTFT at a realistic long prompt
    ttft_target = min(3500, max(targets))
    ttft_prompt = build_prompt(client, ttft_target)
    for _ in range(3):
        t = measure_ttft(client, ttft_prompt)
        if t is not None:
            ttft_samples.append(t)
    if ttft_samples:
        print(f"\nTTFT @{ttft_target} tok prompt: median {statistics.median(ttft_samples):.2f} s  "
              f"(samples {[round(x, 2) for x in ttft_samples]})")

    out = {
        "label": args.label,
        "n_ctx": n_ctx,
        "slots": slots,
        "build": props.get("build_info"),
        "results": [asdict(r) for r in results],
        "ttft_s": [round(x, 3) for x in ttft_samples],
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
