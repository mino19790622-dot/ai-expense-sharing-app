"""OCR / Scan 在鉴权接入后的测试：需登录、端到端、历史落库"""
import json
from io import BytesIO

from PIL import Image


def _png():
    img = Image.new("RGB", (12, 12), (255, 255, 255))
    b = BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _token(client, username="ouser"):
    return client.post(
        "/api/v1/auth/register", json={"username": username, "password": "secret1"}
    ).json()["token"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def test_ocr_requires_auth(client):
    """未带 Bearer token 的 /ocr 必须被挡在 401，而不是落到 mock OCR 后端。"""
    r = client.post("/api/v1/ocr", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 401


def test_ocr_authed(client):
    """登录后 /ocr 返回解析结果；mock 后端固定把 paid_by 报成 u1，故断言写死 u1。"""
    token = _token(client)
    r = client.post("/api/v1/ocr", files={"file": ("r.png", _png(), "image/png")}, headers=_hdr(token))
    assert r.status_code == 200
    assert r.json()["paid_by"] == "u1"  # mock 后端固定返回 u1


def test_scan_authed(client):
    """/scan = OCR + 分摊一次做完：响应里必须同时有 shares 与落库后的 receipt_id。"""
    token = _token(client)
    r = client.post(
        "/api/v1/scan",
        data={"participants": json.dumps([{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}]), "method": "equal"},
        files={"file": ("r.png", _png(), "image/png")},
        headers=_hdr(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert "shares" in body and "receipt_id" in body


def test_scan_bad_image_400(client):
    """非图片 content-type 走 400（参数错），而不是 422 或 500 —— 客户端错误与后端故障要分得开。"""
    token = _token(client)
    r = client.post(
        "/api/v1/scan",
        data={"participants": json.dumps([{"id": "u1", "name": "A"}]), "method": "equal"},
        files={"file": ("r.txt", b"not an image", "text/plain")},
        headers=_hdr(token),
    )
    assert r.status_code == 400


def test_scan_then_history(client):
    """端到端串起来：scan 落库后 /history 必须能看到至少一条（断言用 >=1，不假设库里原本为空）。"""
    token = _token(client)
    client.post(
        "/api/v1/scan",
        data={"participants": json.dumps([{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}]), "method": "equal"},
        files={"file": ("r.png", _png(), "image/png")},
        headers=_hdr(token),
    )
    h = client.get("/api/v1/history", headers=_hdr(token))
    assert h.status_code == 200
    assert len(h.json()) >= 1
