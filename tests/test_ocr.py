"""OCR / Scan 在鉴权接入后的测试：需登录、端到端、历史落库"""
import json
from io import BytesIO

import pytest
from PIL import Image

from app.core.ocr import MockOCRBackend, QwenVLOCRBackend, get_ocr_backend


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


def test_ocr_rejects_non_image_400(client):
    """/ocr 与 /scan 的 content-type 闸门必须一致：非图片一律 400，且给出可读的 detail。

    这个分支此前零覆盖 —— 断言 detail 里点名了 image/，避免以后被改成笼统的「参数错误」。
    """
    token = _token(client, username="oimg")
    r = client.post(
        "/api/v1/ocr",
        files={"file": ("r.txt", b"not an image", "text/plain")},
        headers=_hdr(token),
    )
    assert r.status_code == 400
    assert "image/" in r.json()["detail"]


def test_scan_bad_participants_json_400(client):
    """participants 不是合法 JSON 数组时走 400（解析失败），而不是 422 或 500。

    真实前端是把这个字段当字符串表单传的，序列化出错属于客户端问题，
    必须落在 400 这一侧，才能和「后端炸了」区分开。
    """
    token = _token(client, username="obad")
    r = client.post(
        "/api/v1/scan",
        data={"participants": "not json", "method": "equal"},
        files={"file": ("r.png", _png(), "image/png")},
        headers=_hdr(token),
    )
    assert r.status_code == 400
    assert "participants" in r.json()["detail"]


def test_scan_explicit_paid_by_beats_mock_result(client):
    """显式传 paid_by=u2 时，回传的 receipt.paid_by 必须被改写为 u2。

    mock OCR 后端固定把 paid_by 报成 u1，所以这条用例真正验证的是
    routes.py 里「用户显式选择 > 模型推测」这条优先级 —— 不是 OCR 的输出。
    """
    token = _token(client, username="opay1")
    r = client.post(
        "/api/v1/scan",
        data={
            "participants": json.dumps([{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}]),
            "method": "equal",
            "paid_by": "u2",
        },
        files={"file": ("r.png", _png(), "image/png")},
        headers=_hdr(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["receipt"]["paid_by"] == "u2"
    assert body["paid_by"] == "u2"


def test_scan_falls_back_to_first_participant_when_paid_by_is_ghost(client):
    """paid_by 不在参与者白名单里时，回落到 participants[0].id，绝不留下幽灵 id。

    用 x1/x2 而不是 u1/u2：mock 返回的 u1 若留在参与者集合里，
    「不在白名单」这个条件根本不会成立，测试就会假通过。
    """
    token = _token(client, username="opay2")
    r = client.post(
        "/api/v1/scan",
        data={
            "participants": json.dumps([{"id": "x1", "name": "X"}, {"id": "x2", "name": "Y"}]),
            "method": "equal",
            "paid_by": "ghost",
        },
        files={"file": ("r.png", _png(), "image/png")},
        headers=_hdr(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["receipt"]["paid_by"] == "x1"
    assert "ghost" not in body["shares"]


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


# ---------------------------------------------------------------------------
# 后端选择器的契约（app/core/ocr.py::get_ocr_backend）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    ["qwen-vl", "qwen_vl", "qwen ", " qwen", "real", "openai", "vlm", "qwen2", "", "MO"],
)
def test_ocr_backend_falls_back_to_mock_for_unknown_values(monkeypatch, value):
    """除了精确的 qwen，任何 OCR_BACKEND 取值都静默回落 mock，不报错也不告警。

    这条钉住「拼错环境变量不失败、只会拿到假收据」这个事实 ——
    qwen-vl / 带空格的 qwen 都是运维很容易写出来的。
    """
    monkeypatch.setenv("OCR_BACKEND", value)
    assert isinstance(get_ocr_backend(), MockOCRBackend)


@pytest.mark.parametrize("value", ["qwen", "QWEN", "Qwen"])
def test_ocr_backend_selects_qwen_case_insensitively(monkeypatch, value):
    """后端名比对前会 .lower()，所以 QWEN / Qwen 与 qwen 等价。"""
    monkeypatch.setenv("OCR_BACKEND", value)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test-not-a-real-key")
    assert isinstance(get_ocr_backend(), QwenVLOCRBackend)


def test_qwen_backend_without_api_key_raises_runtime_error(monkeypatch):
    """选了 qwen 却没配 DASHSCOPE_API_KEY 时抛 RuntimeError —— 不是 ValueError。

    路由的 except ValueError 抓不到它 ⇒ /ocr 与 /scan 会返回 500 而非 400。
    断言异常类型本身就是为了把这个「配置错误伪装成服务端故障」的事实钉住。
    """
    monkeypatch.setenv("OCR_BACKEND", "qwen")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        get_ocr_backend()
    assert not isinstance(exc.value, ValueError)
    assert "DASHSCOPE_API_KEY" in str(exc.value)
