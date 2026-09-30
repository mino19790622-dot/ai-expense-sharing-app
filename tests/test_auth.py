"""鉴权流程测试：注册 / 登录 / 当前用户 / 非法令牌"""


def test_register_and_login(client):
    """注册即签发可用令牌；重名 409，登录成功换发新令牌，密码错误 401。"""
    r = client.post("/api/v1/auth/register", json={"username": "alice", "password": "secret1"})
    assert r.status_code == 200
    data = r.json()
    assert data["token"] and data["user"]["username"] == "alice"
    token = data["token"]

    # 注册时签发的令牌应当立即可用，不必先走一次登录
    r_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200 and r_me.json()["username"] == "alice"

    # 重名注册 -> 409
    r2 = client.post("/api/v1/auth/register", json={"username": "alice", "password": "secret1"})
    assert r2.status_code == 409

    # 登录成功
    r3 = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret1"})
    assert r3.status_code == 200 and r3.json()["token"]

    # 密码错误 -> 401
    r4 = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong"})
    assert r4.status_code == 401


def test_me_requires_and_accepts_token(client):
    """/me 带合法令牌返回本人；缺令牌或伪造令牌一律 401。"""
    token = client.post(
        "/api/v1/auth/register", json={"username": "bob", "password": "secret1"}
    ).json()["token"]

    # 带令牌
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["username"] == "bob"

    # 无令牌 -> 401
    assert client.get("/api/v1/auth/me").status_code == 401

    # 伪造令牌 -> 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_password_validation(client):
    """过短的密码应在注册阶段被拒（400），不得落库。"""
    # 密码太短
    r = client.post("/api/v1/auth/register", json={"username": "x", "password": "123"})
    assert r.status_code == 400
