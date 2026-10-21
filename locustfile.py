"""
Stage 5 — Locust 压测脚本（工业级，简历/演示用）
================================================
安装：  pip install -r requirements-dev.txt
运行：  locust -f locustfile.py --host http://localhost:8080
        # 然后打开 http://localhost:8089 调 UI，或用无头模式：
        locust -f locustfile.py --host http://localhost:8080 \
               --headless -u 100 -r 20 -t 30s --csv=report

含义：模拟 100 个并发用户（每秒起 20 个），跑 30 秒，
      3/4 流量打 /health，1/4 打 /split，产 QPS / 响应时间分布报告。
"""
from locust import HttpUser, between, task


class ExpenseUser(HttpUser):
    wait_time = between(0.1, 0.5)  # 每个用户请求间隔 0.1~0.5s

    @task(3)  # 权重 3：更频繁地打轻量健康检查
    def health(self):
        """健康检查：**唯一不需要鉴权**的端点（`app/main.py:47`），所以也是唯一一条
        真正走到应用代码的压测流量 —— 它返回常量 dict，p99 只反映框架 + 中间件开销。
        """
        self.client.get("/health")

    @task(1)  # 权重 1：较少地打分账接口（更重）
    def split(self):
        """分账压测：⚠️ **当前这条流量全部是 404，不是分账延迟**。

        路径 `/split` 是 Stage 5 的旧写法；Stage 6 把业务路由挂到
        `APIRouter(prefix="/api/v1")`（`app/api/routes.py:22`），真实端点是
        `/api/v1/split`，且带 `Depends(get_current_user)`（`routes.py:83`）。

        实测（`TestClient`，空库）：`POST /split` → **404**；`POST /api/v1/split`
        无 token → **401**。所以 locust 报表里 split 那一行的 p50/p99 是
        「路由未命中」的往返耗时，与 `compute()` 的 CPU 成本无关。

        要修得同时改两处 —— 路径换成 `/api/v1/split`，并在 `on_start` 里用
        `POST /api/v1/auth/login` 拿 Bearer token 塞进 headers；否则改完路径仍是 401。
        这属改压测口径、会改变已有报表的可比性，故此处**只记录、不改动**。
        """
        payload = {
            "receipt": {
                "items": [{"description": "pizza", "amount": 30, "assigned_to": ["u1", "u2"]}],
                "tax": 3,
                "paid_by": "u1",
            },
            "participants": [{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}],
            "method": "equal",
        }
        self.client.post("/split", json=payload)
