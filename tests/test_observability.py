import json

from fastapi.testclient import TestClient

from app.main import app


def test_access_log_writes_jsonl(tmp_path, monkeypatch):
    """设了 ACCESS_LOG_FILE 后，每个请求应追加一行 JSON 日志。"""
    log_file = tmp_path / "access.log"
    # 中间件在 dispatch 时才读 env，所以请求前设好即可
    monkeypatch.setenv("ACCESS_LOG_FILE", str(log_file))

    client = TestClient(app)
    client.get("/health")

    lines = log_file.read_text().strip().splitlines()
    assert lines, "access log 不应为空"
    rec = json.loads(lines[-1])  # 应能解析为一行 JSON
    assert rec["path"] == "/health"
    assert rec["status"] == 200
    assert "latency_ms" in rec
