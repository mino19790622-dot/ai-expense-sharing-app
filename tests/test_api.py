"""业务路由在鉴权接入后的测试：需登录、分账、结算、非法策略"""


def _token(client, username="user1"):
    return client.post(
        "/api/v1/auth/register", json={"username": username, "password": "secret1"}
    ).json()["token"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


_RECEIPT = {
    "items": [{"description": "Pizza", "amount": 30.0, "assigned_to": []}],
    "tax": 0.0,
    "paid_by": "u1",
}


def test_split_requires_auth(client):
    body = {"receipt": _RECEIPT, "participants": [{"id": "u1", "name": "A"}], "method": "equal"}
    assert client.post("/api/v1/split", json=body).status_code == 401


def test_split_ok_and_saved(client):
    token = _token(client)
    body = {"receipt": _RECEIPT, "participants": [{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}], "method": "equal"}
    r = client.post("/api/v1/split", json=body, headers=_hdr(token))
    assert r.status_code == 200
    assert r.json()["total"] == 30.0
    assert r.json()["saved"] is True


def test_split_bad_method_400(client):
    token = _token(client)
    body = {"receipt": _RECEIPT, "participants": [{"id": "u1", "name": "A"}], "method": "nonsense"}
    r = client.post("/api/v1/split", json=body, headers=_hdr(token))
    assert r.status_code == 400


def test_settle_ok(client):
    token = _token(client)
    r = client.post(
        "/api/v1/settle",
        json={"shares": {"u1": 40, "u2": 40, "u3": 20}, "paid_by": "u1", "total": 100},
        headers=_hdr(token),
    )
    assert r.status_code == 200
    assert "transfers" in r.json()
