"""两步式流程：/ocr 识别 → 前端编辑 assigned_to → /confirm 结算并落库

覆盖的点：
  1. 端点需要登录
  2. per_item 真正尊重 assigned_to（谁点的菜算谁头上）
  3. 收据与分账一起落库，且能在历史里追溯（/split 落库时 receipt_id 为 NULL，做不到这点）
"""


def _token(client, username="cuser"):
    """注册一个新用户并取回 token。

    每次调用都走 /register，所以同一个 client 里重复调用会撞「用户名已存在」——
    需要多个身份时应传不同的 username。
    """
    return client.post(
        "/api/v1/auth/register", json={"username": username, "password": "secret1"}
    ).json()["token"]


def _hdr(token):
    """把裸 token 包成端点要求的 Bearer 头。"""
    return {"Authorization": f"Bearer {token}"}


_PEOPLE = [{"id": "u1", "name": "Alice"}, {"id": "u2", "name": "Bob"}]


def _body(receipt, method="per_item", people=None):
    """拼 /confirm 的请求体；people 传 None 时用默认的两人组。"""
    return {"receipt": receipt, "participants": people or _PEOPLE, "method": method}


def test_confirm_requires_auth(client):
    """不带 Authorization 头 → 401；请求体本身是合法的，确保拦截发生在鉴权而非校验阶段。"""
    receipt = {
        "items": [{"description": "Pizza", "amount": 30.0, "assigned_to": []}],
        "tax": 0.0,
        "paid_by": "u1",
    }
    assert client.post("/api/v1/confirm", json=_body(receipt)).status_code == 401


def test_confirm_per_item_respects_assigned_to(client):
    """Pizza 只勾了 Bob，Coke 没勾（全员平摊）→ Bob 30+6，Alice 6。"""
    token = _token(client)
    receipt = {
        "items": [
            {"description": "Pizza", "amount": 30.0, "assigned_to": ["u2"]},
            {"description": "Coke", "amount": 12.0, "assigned_to": []},
        ],
        "tax": 0.0,
        "paid_by": "u1",
    }
    r = client.post("/api/v1/confirm", json=_body(receipt), headers=_hdr(token))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 42.0
    assert body["shares"]["u2"] == 36.0   # 30（独自）+ 6（平摊）
    assert body["shares"]["u1"] == 6.0    # 只出平摊的一半
    # 分配结果要原样回显，前端才能确认「谁点了什么」记对了
    assert body["receipt"]["items"][0]["assigned_to"] == ["u2"]


def test_confirm_unassigned_falls_back_to_equal(client):
    """一道菜都不勾 → 所有菜全员平摊，结果与 equal 一致。"""
    token = _token(client)
    receipt = {
        "items": [{"description": "Pizza", "amount": 30.0, "assigned_to": []}],
        "tax": 0.0,
        "paid_by": "u1",
    }
    r = client.post("/api/v1/confirm", json=_body(receipt), headers=_hdr(token))
    assert r.status_code == 200
    assert r.json()["shares"] == {"u1": 15.0, "u2": 15.0}


def test_confirm_persists_receipt_and_shows_in_history(client):
    """确认后返回非空 receipt_id，且该笔能在 /history 里按 shares 追溯。

    历史断言用 `len(rows) >= 1` 而不假设空库，避免与其它测试共用的临时库互相干扰；
    取 rows[0] 是因为 /history 按**收据**创建时间倒序，本次刚落的就是最新一条。
    """
    token = _token(client)
    receipt = {
        "items": [{"description": "Pizza", "amount": 30.0, "assigned_to": ["u2"]}],
        "tax": 0.0,
        "paid_by": "u1",
    }
    r = client.post("/api/v1/confirm", json=_body(receipt), headers=_hdr(token))
    assert r.status_code == 200
    assert r.json()["receipt_id"] is not None

    h = client.get("/api/v1/history", headers=_hdr(token))
    assert h.status_code == 200
    rows = h.json()
    assert len(rows) >= 1
    assert rows[0]["method"] == "per_item"
    assert rows[0]["shares"]["u2"] == 30.0


def test_confirm_bad_method_400(client):
    """未知 method 由 compute() 抛 ValueError，路由层捕获后转 400（不是 422 也不是 500）。"""
    token = _token(client)
    receipt = {
        "items": [{"description": "Pizza", "amount": 30.0, "assigned_to": []}],
        "tax": 0.0,
        "paid_by": "u1",
    }
    r = client.post(
        "/api/v1/confirm", json=_body(receipt, method="nonsense"), headers=_hdr(token)
    )
    assert r.status_code == 400
