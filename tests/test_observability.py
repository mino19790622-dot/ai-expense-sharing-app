"""Stage 5 可观测性：访问日志中间件的端到端校验。

覆盖 ``AccessLogMiddleware`` 的两条契约：
  1. 设了 ``ACCESS_LOG_FILE`` → 每个请求往该文件追加一行 JSON（JSONL）；
  2. 每行记录至少含 ``method`` / ``path`` / ``status`` / ``latency_ms`` / ``client``。

⚠️ 加新测试时注意：``app`` 是模块级单例，中间件实例在**首次 dispatch** 时
才打开文件并把句柄缓存在 ``_fh`` 上，之后不再读环境变量。所以「换一个
``ACCESS_LOG_FILE`` 再断言另一个文件」的写法会失败——第二个用例仍在写第一个
用例的句柄。要验证别的分支，必须在同一个用例内复用同一路径，或显式重置
``app.middleware_stack._fh``。
"""
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
    client.get("/health")  # 第二次请求用于验证「追加」而非「覆盖」

    lines = log_file.read_text().strip().splitlines()
    assert lines, "access log 不应为空"
    assert len(lines) == 2, f"两次请求应追加两行，实际 {len(lines)} 行"
    rec = json.loads(lines[-1])  # 应能解析为一行 JSON
    assert rec["path"] == "/health"
    assert rec["method"] == "GET"
    assert rec["status"] == 200
    assert "latency_ms" in rec
    assert "client" in rec  # TestClient 下为占位主机名，此处只校验字段存在
