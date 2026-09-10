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
from locust import HttpUser, task, between


class ExpenseUser(HttpUser):
    wait_time = between(0.1, 0.5)  # 每个用户请求间隔 0.1~0.5s

    @task(3)  # 权重 3：更频繁地打轻量健康检查
    def health(self):
        self.client.get("/health")

    @task(1)  # 权重 1：较少地打分账接口（更重）
    def split(self):
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
