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
    r = client.post("/api/v1/ocr", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 401


def test_ocr_authed(client):
    token = _token(client)
    r = client.post("/api/v1/ocr", files={"file": ("r.png", _png(), "image/png")}, headers=_hdr(token))
    assert r.status_code == 200
    assert r.json()["paid_by"] == "u1"  # mock 后端固定返回 u1


def test_scan_authed(client):
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
    token = _token(client)
    r = client.post(
        "/api/v1/scan",
        data={"participants": json.dumps([{"id": "u1", "name": "A"}]), "method": "equal"},
        files={"file": ("r.txt", b"not an image", "text/plain")},
        headers=_hdr(token),
    )
    assert r.status_code == 400


def test_scan_then_history(client):
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
