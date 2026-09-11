"""
Stage 4 — OCR / VLM 收据解析
================================
职责：把一张收据图片（bytes）转成 Stage 1 已经定义好的 Receipt 对象。

设计要点（面试能讲的点）：
  1. 后端可插拔：同一个 extract_receipt() 入口，底层可以是 Mock（离线/测试）
     或真实 Qwen-VL（生产）。调用方完全无感 —— 这是「依赖倒置 / 策略模式」。
  2. 用环境变量 OCR_BACKEND 切换后端，不改动业务代码 —— 「开闭原则」。
  3. 真实后端只在需要时联网；离线/CI 全程用 mock，保证测试稳定、可复现。
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import List, Protocol

from app.core.split import LineItem, Receipt


# ---------------------------------------------------------------------------
# 1. 后端协议：任何 OCR 后端都要实现 extract()
#    Protocol 相当于「接口契约」，静态检查能拦住实现不一致的后端。
# ---------------------------------------------------------------------------
class OCRBackend(Protocol):
    def extract(self, image_bytes: bytes) -> Receipt:
        ...


# ---------------------------------------------------------------------------
# 2. Mock 后端：不联网，返回一份写死的收据
#    用途：本地开发、单元测试、没有 API key 时也能跑通整条链路。
#    真实项目里这里会换成 VLM，但接口不变，调用方无感。
# ---------------------------------------------------------------------------
class MockOCRBackend:
    def extract(self, image_bytes: bytes) -> Receipt:
        # 故意让金额随图片字节长度波动，方便肉眼验证「链路确实穿过了图片」。
        size = len(image_bytes)
        pizza_price = 30.0 + (size % 10)  # 30 ~ 39 之间
        return Receipt(
            items=[
                LineItem(description="Pizza", amount=pizza_price, assigned_to=[]),
                LineItem(description="Coke", amount=12.0, assigned_to=[]),
                # 注意：assigned_to 一律留空 —— 收据照片不会写「谁点了这道菜」，
                # 归属只能由用户在前端勾选后回填（见 /api/v1/confirm）。
                LineItem(description="Salad", amount=18.0, assigned_to=[]),
            ],
            tax=6.0,
            paid_by="u1",
        )


# ---------------------------------------------------------------------------
# 3. 真实后端：调用阿里 DashScope 的 Qwen-VL（OpenAI 兼容模式）
#    需要环境变量 DASHSCOPE_API_KEY。
# ---------------------------------------------------------------------------
class QwenVLOCRBackend:
    def __init__(self) -> None:
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise RuntimeError("缺少环境变量 DASHSCOPE_API_KEY，无法使用 Qwen-VL 后端")
        # 懒加载 httpx：没装时也不影响离线路径（mock 后端用不到它）
        import httpx  # noqa: F401

        self._httpx = httpx

    def extract(self, image_bytes: bytes) -> Receipt:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        mime = self._mime(image_bytes)
        data_url = f"data:{mime};base64,{b64}"

        prompt = (
            "这是一张消费收据图片。请从中提取结构化信息，"
            "严格只返回如下 JSON（不要任何解释、不要代码块标记）：\n"
            '{\n'
            '  "items": [{"description": "菜品名", "amount": 金额数字, "assigned_to": []}],\n'
            '  "tax": 税额数字,\n'
            '  "paid_by": "垫付人id",\n'
            '  "total": 总金额数字\n'
            "}\n"
            "规则：\n"
            "1. amount / tax / total 必须是纯数字（不要货币符号）。\n"
            "2. items 不能为空；如果图片里只有一行合计，则 items=[{\"description\":\"Total\",\"amount\":总金额,\"assigned_to\":[]}]。\n"
            "3. tax 从 SST / GST / Tax / Service Charge 等行提取，没有就写 0。\n"
            "4. paid_by 是垫付人 id（u1/u2/...）；如果收据上没有明确写谁垫付，就写空字符串 \"\"。\n"
            "5. assigned_to 空数组 [] 表示该项由所有人平摊。"
        )

        payload = {
            # 模型可由 OCR_MODEL 环境变量覆盖（默认 qwen-vl-max）
            "model": os.getenv("OCR_MODEL", "qwen-vl-max"),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = self._httpx.post(url, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            # 把上游错误透传出来，方便定位（key 失效 / 额度用尽 / 模型名错）
            raise ValueError(f"Qwen-VL 调用失败 HTTP {resp.status_code}: {resp.text[:300]}")
        content = resp.json()["choices"][0]["message"]["content"]
        return self._parse(content)

    @staticmethod
    def _mime(image_bytes: bytes) -> str:
        """根据文件头猜 mime，避免把 PNG 当成 JPEG 发给模型。"""
        if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        # 其他（含 JPEG 的 \xff\xd8\xff）一律按 jpeg 兜底
        return "image/jpeg"

    @staticmethod
    def _parse(content: str) -> Receipt:
        """VLM 常会裹一层 ```json 代码块，这里稳健地抠出纯 JSON。"""
        cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"VLM 未返回可解析的 JSON: {content!r}")
        data = json.loads(cleaned[start : end + 1])

        raw_items = data.get("items") or []
        if not raw_items:
            total = float(data.get("total", 0.0))
            tax = float(data.get("tax", 0.0))
            raw_items = [{"description": "Total", "amount": max(0.0, total - tax), "assigned_to": []}]

        items = [
            LineItem(
                description=it["description"],
                amount=float(it["amount"]),
                assigned_to=it.get("assigned_to", []) or [],
            )
            for it in raw_items
        ]
        paid_by = data.get("paid_by")
        if paid_by is None:
            paid_by = ""
        return Receipt(
            items=items,
            tax=float(data.get("tax", 0.0)),
            paid_by=str(paid_by),
        )


# ---------------------------------------------------------------------------
# 4. 工厂：根据环境变量选择后端（默认 mock，离线即可跑）
# ---------------------------------------------------------------------------
def get_ocr_backend() -> OCRBackend:
    name = os.getenv("OCR_BACKEND", "mock").lower()
    if name == "qwen":
        return QwenVLOCRBackend()
    return MockOCRBackend()


# ---------------------------------------------------------------------------
# 5. 统一入口：业务代码只调这个，不关心底层是 mock 还是 VLM
# ---------------------------------------------------------------------------
def extract_receipt(image_bytes: bytes) -> Receipt:
    if not image_bytes:
        raise ValueError("图片内容为空")
    return get_ocr_backend().extract(image_bytes)
