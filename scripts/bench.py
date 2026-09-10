"""
Stage 5 — 轻量压测脚本（零额外依赖，复用已装的 httpx）
=====================================================
用法：
    python scripts/bench.py --path /health --requests 2000 --concurrency 100
    python scripts/bench.py --path /split  --method POST --requests 500 --concurrency 50

它会并发打 N 个请求，最后输出：QPS、p50/p95/p99 延迟（毫秒）。
为什么自己写而不直接用 locust：这个脚本只依赖 httpx，跑起来快、结果可复现，
适合本地快速验证；locustfile.py 才是给简历/演示用的工业级工具。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time

import httpx


_SPLIT_BODY = {
    "receipt": {
        "items": [{"description": "pizza", "amount": 30, "assigned_to": ["u1", "u2"]}],
        "tax": 3,
        "paid_by": "u1",
    },
    "participants": [{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}],
    "method": "equal",
}


async def _worker(client, path, sem, latencies, method):
    async with sem:
        t0 = time.perf_counter()
        try:
            if method == "POST":
                await client.post(path, json=_SPLIT_BODY)
            else:
                await client.get(path)
        except Exception:
            pass
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, int(round((p / 100) * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--path", default="/health")
    ap.add_argument("--method", default="GET")
    ap.add_argument("--requests", type=int, default=1000)
    ap.add_argument("--concurrency", type=int, default=50)
    args = ap.parse_args()

    latencies: list[float] = []
    sem = asyncio.Semaphore(args.concurrency)
    limits = httpx.Limits(max_connections=args.concurrency)

    async with httpx.AsyncClient(base_url=args.url, limits=limits, timeout=30) as client:
        t0 = time.perf_counter()
        tasks = [
            _worker(client, args.path, sem, latencies, args.method)
            for _ in range(args.requests)
        ]
        await asyncio.gather(*tasks)
        wall = time.perf_counter() - t0

    s = sorted(latencies)
    print(json.dumps({
        "endpoint": f"{args.method} {args.url}{args.path}",
        "total_requests": args.requests,
        "concurrency": args.concurrency,
        "duration_s": round(wall, 3),
        "qps": round(args.requests / wall, 1),
        "p50_ms": round(_percentile(s, 50), 2),
        "p95_ms": round(_percentile(s, 95), 2),
        "p99_ms": round(_percentile(s, 99), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
