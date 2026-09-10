"""
Stage 5 — 可观测性：JSONL 访问日志中间件
=========================================
职责：给每个 HTTP 请求记一条结构化日志（一行一个 JSON），包含
      method / path / status / latency_ms / client。
为什么重要：没有日志你就「看不见」服务在跑什么、慢在哪——这是后端工程的基本功。

设计要点：
  1. 用 Starlette 的 BaseHTTPMiddleware，对业务代码零侵入（一行 add_middleware 即可）。
  2. 日志落地位置由环境变量决定：
       - 设了 ACCESS_LOG_FILE  → 写文件（JSONL，每行一个 JSON，方便后续用 jq/ELK 分析）
       - 没设                  → 打到 stdout（容器环境里 stdout 会被 docker/colima 收集）
  3. 文件句柄「懒打开 + 线程锁」，避免每次请求都 open/close，也不在多worker下写串。
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class AccessLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._fh = None           # 懒加载的文件句柄
        self._lock = threading.Lock()

    def _get_fh(self):
        # 第一次请求时才打开文件（此时环境变量必然已就绪），之后复用同一句柄
        if self._fh is None:
            path = os.getenv("ACCESS_LOG_FILE")
            if path:
                self._fh = open(path, "a", encoding="utf-8")
        return self._fh

    async def dispatch(self, request: Request, call_next: Callable):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        # 一条结构化记录 = 一行 JSON（JSONL 格式）
        record = {
            "ts": round(time.time(), 3),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round(elapsed_ms, 2),
            "client": request.client.host if request.client else None,
        }
        line = json.dumps(record, ensure_ascii=False)

        fh = self._get_fh()
        if fh:
            with self._lock:
                fh.write(line + "\n")
                fh.flush()
        else:
            # 默认打到 stdout（容器里会被日志驱动收集）
            print(line, flush=True)

        return response
