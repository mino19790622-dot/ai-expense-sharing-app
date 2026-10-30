"""业务路由在鉴权接入后的测试：需登录、分账、结算、非法策略"""


def _token(client, username="user1"):
    """注册一个新用户并返回其 token。

    依赖 conftest 的临时库：每个测试拿到的是空库，所以同一个 username
    可以反复注册；若改成共享库，这里必须先 login 再 register。
    """
    return client.post(
        "/api/v1/auth/register", json={"username": username, "password": "secret1"}
    ).json()["token"]


def _hdr(token):
    """把 token 包成 Bearer 头；与 app/core/auth.py 的解析格式保持一致。"""
    return {"Authorization": f"Bearer {token}"}


_RECEIPT = {
    "items": [{"description": "Pizza", "amount": 30.0, "assigned_to": []}],
    "tax": 0.0,
    "paid_by": "u1",
}


def test_split_requires_auth(client):
    """不带 token 时 /split 直接 401，不会走到 compute() 或落库。"""
    body = {"receipt": _RECEIPT, "participants": [{"id": "u1", "name": "A"}], "method": "equal"}
    assert client.post("/api/v1/split", json=body).status_code == 401


def test_split_ok_and_saved(client):
    """/split 的成功路径：返回 total 与 saved=True。

    注意 saved 是路由硬编码的 True，表示「已调过 save_split」，
    而不是数据库返回的行数 —— 所以这里只断言布尔值。
    """
    token = _token(client)
    body = {"receipt": _RECEIPT, "participants": [{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}], "method": "equal"}
    r = client.post("/api/v1/split", json=body, headers=_hdr(token))
    assert r.status_code == 200
    assert r.json()["total"] == 30.0
    assert r.json()["saved"] is True


def test_split_bad_method_400(client):
    """未知策略由 compute() 抛 ValueError，路由转成 400（不是 422/500）。"""
    token = _token(client)
    body = {"receipt": _RECEIPT, "participants": [{"id": "u1", "name": "A"}], "method": "nonsense"}
    r = client.post("/api/v1/split", json=body, headers=_hdr(token))
    assert r.status_code == 400


def test_settle_ok(client):
    """/settle 只透传 debt.settle()，此处仅确认返回体带 transfers 字段。

    份额 40/40/20 由 u1 垫付 100 ⇒ 期望 u2、u3 各转一笔给 u1；
    具体笔数由贪心算法决定，不在本测试的断言范围内。
    """
    token = _token(client)
    r = client.post(
        "/api/v1/settle",
        json={"shares": {"u1": 40, "u2": 40, "u3": 20}, "paid_by": "u1", "total": 100},
        headers=_hdr(token),
    )
    assert r.status_code == 200
    assert "transfers" in r.json()
