"""Stage 5 可观测性：访问日志中间件的端到端校验。

覆盖 ``AccessLogMiddleware`` 的两条契约：
  1. 设了 ``ACCESS_LOG_FILE`` → 每个请求往该文件追加一行 JSON（JSONL）；
  2. 每行记录至少含 ``method`` / ``path`` / ``status`` / ``latency_ms`` / ``client``。

⚠️ 加新测试时注意：``app`` 是模块级单例，中间件实例在**首次 dispatch** 时
才打开文件并把句柄缓存在 ``_fh`` 上，之后不再读环境变量。所以「换一个
``ACCESS_LOG_FILE`` 再断言另一个文件」的写法会失败——第二个用例仍在写第一个
用例的句柄。

要验证别的分支，得重置**句柄真正所在的那一层**：``app.middleware_stack``
是外层的 ``ServerErrorMiddleware``，它没有 ``_fh``，往上赋值只会凭空多出一个
无用属性、句柄照旧；中间件实例在它内层，即 ``app.middleware_stack.app``。
置 ``app.middleware_stack.app._fh = None`` 才会让下一次请求重新按环境变量开文件。
"""
import json

from fastapi.testclient import TestClient

from app.core.middleware import AccessLogMiddleware
from app.main import app


def _access_log_middleware() -> AccessLogMiddleware:
    """沿 middleware 链找到 ``AccessLogMiddleware`` 实例（句柄 ``_fh`` 挂在它身上）。"""
    node = app.middleware_stack
    while node is not None and not isinstance(node, AccessLogMiddleware):
        node = getattr(node, "app", None)
    assert node is not None, "app 上未挂载 AccessLogMiddleware"
    return node


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


def test_log_handle_survives_env_change_until_reset(tmp_path, monkeypatch):
    """句柄一旦打开就按契约缓存：改环境变量不换文件，显式置 ``_fh = None`` 才会。"""
    client = TestClient(app)
    client.get("/health")  # 先打一次，触发 middleware_stack 构建（此时还没设 ACCESS_LOG_FILE）
    mw = _access_log_middleware()
    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    saved_fh, mw._fh = mw._fh, None  # 从干净状态起跑，结束时还原，避免污染其他用例
    try:
        monkeypatch.setenv("ACCESS_LOG_FILE", str(first))
        client.get("/health")
        client.get("/health")
        assert len(first.read_text().splitlines()) == 2

        # 换路径但不重置句柄：仍写旧文件，新文件根本不会出现
        monkeypatch.setenv("ACCESS_LOG_FILE", str(second))
        client.get("/health")
        assert not second.exists(), "句柄已缓存，不应改写到新路径"
        assert len(first.read_text().splitlines()) == 3

        # 显式重置句柄后才按新环境变量开文件
        mw._fh = None
        client.get("/health")
        assert second.exists(), "重置 _fh 后应按新环境变量开新文件"
        assert len(second.read_text().splitlines()) == 1
    finally:
        mw._fh = saved_fh
