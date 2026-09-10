# 压测报告（Stage 5）

环境：macOS 沙箱（loader 与 server 共用同一份受限 CPU），uvicorn 单/4 worker。
工具：`scripts/bench.py`（httpx + asyncio，零额外依赖）；工业级见 `locustfile.py`。

## 测得数据

| 端点 | 配置 | QPS | p50 | p95 | p99 | max |
|------|------|-----|-----|-----|-----|-----|
| GET /health | 1 worker, 100 并发, 2000 req | 128.5 | 445ms | 2564ms | 5155ms | 8981ms |
| POST /split | 1 worker, 50 并发, 500 req | 88.3 | 323ms | 1625ms | 2441ms | 3757ms |
| GET /health | 4 worker, 100 并发, 2000 req | 134.9 | 404ms | 2416ms | 5004ms | 7750ms |

## 为什么这样设计 / 结论

1. **瓶颈是「压测机与服务抢同一份受限 CPU」，不是应用本身。**
   把 worker 从 1 加到 4，QPS 几乎不变（128→135）。若瓶颈在服务端，加 worker 应显著提
   升吞吐；没提升说明单进程 benchmark 客户端（asyncio）自己先被 CPU 打满，且新增的 3 个
   worker 反而和它抢核。→ **在 sandbox 里这份数字不反映生产容量**，只反映「同机竞争」。

2. **真实容量要在「负载发生器与待测服务分离」的环境里重测**（独立机器或容器配额隔离）。
   届时 `/health`（纯内存返回）与 `/split`（纯 CPU 整数运算）都应轻松到数千~上万 QPS。
   真正会变慢的是 `/ocr`、`/scan`——它们要走网络调外部 VLM，延迟由第三方 API 决定，
   届时应加超时、重试、并发上限与缓存。

3. **可观测性已就位**：每个请求都会落一条 JSONL 访问日志（method/path/status/latency_ms），
   默认打到 stdout（容器日志驱动会收集），设 `ACCESS_LOG_FILE=path` 则写文件，方便后续接
   jq / ELK 做延迟分布与错误率分析。

## 怎么复现

```bash
# 1) 起服务
uvicorn app.main:app --port 8080            # 或 docker compose up --build

# 2) 轻量压测（无需装额外包）
python scripts/bench.py --path /health --requests 2000 --concurrency 100
python scripts/bench.py --path /split  --method POST --requests 500 --concurrency 50

# 3) 工业级（简历/演示）：先 pip install -r requirements-dev.txt
locust -f locustfile.py --host http://localhost:8080 --headless -u 100 -r 20 -t 30s --csv=report

# 4) 落盘访问日志
ACCESS_LOG_FILE=access.log uvicorn app.main:app --port 8080
```
