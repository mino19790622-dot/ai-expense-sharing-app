"""
Stage 6 接入鉴权后的业务路由
============================
所有操作类端点现在都要求登录（get_current_user 依赖），
并且会把收据 / 分账结果落库，做到多用户隔离。
"""
import json
from typing import List, Dict, Any

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends

# 复用 Stage 1/2 的成果：模型来自 split，算法来自 split + debt
from app.core.split import compute, Receipt, Participant
from app.core.debt import settle
# Stage 4 新增：图片 -> Receipt 的解析能力
from app.core.ocr import extract_receipt
# Stage 6 新增：鉴权依赖 + 存储
from app.core.auth import get_current_user
from app.core import db

router = APIRouter(prefix="/api/v1", tags=["splitting"])


# ---------------------------------------------------------------------------
# 请求体的数据模型（Pydantic）
# ---------------------------------------------------------------------------
class SplitRequest(BaseModel):
    receipt: Receipt                              # 直接复用 Stage 1 的 Receipt 模型
    participants: List[Participant]              # 直接参与的人
    method: str = Field(                        # 分账策略
        ...,
        description="equal | per_item | proportional | weighted",
    )


class SettleRequest(BaseModel):
    shares: Dict[str, float]    # compute() 返回的 "shares" 字段
    paid_by: str                # 谁先垫付了整单
    total: float                # 整单总额


class ConfirmRequest(BaseModel):
    """两步式流程第二步的请求体：前端把「已分配好归属」的收据回传。

    与 SplitRequest 结构相同，但语义不同：这里的 receipt.items[].assigned_to
    带着用户在界面上勾选的「谁点了这道菜」，且结算结果会连带收据一起落库。
    """
    receipt: Receipt
    participants: List[Participant]
    method: str = Field("per_item", description="equal | per_item | proportional | weighted")


# ---------------------------------------------------------------------------
# 共用：算分账 + 收据/分账一起落库（/scan 与 /confirm 复用，避免逻辑分叉）
# ---------------------------------------------------------------------------
def _split_and_persist(
    user: dict,
    receipt: Receipt,
    people: List[Participant],
    method: str,
    filename,
) -> Dict[str, Any]:
    """把一张收据算成分账结果，并把「收据 + 分账」关联落库。

    收据的 items_json 会原样保存 assigned_to，
    因此「谁点了哪道菜」的分配结果是可追溯的（历史里能查到）。
    """
    result = compute(receipt, people, method)
    items_json = json.dumps([it.model_dump() for it in receipt.items])
    receipt_id = db.save_receipt(
        user["id"], filename, result["total"], receipt.paid_by, items_json
    )
    db.save_split(user["id"], receipt_id, method, json.dumps(result["shares"]))
    result["receipt_id"] = receipt_id
    result["receipt"] = receipt.model_dump()
    return result


# ---------------------------------------------------------------------------
# 路由 1：分账
# ---------------------------------------------------------------------------
@router.post("/split")
def post_split(
    req: SplitRequest,
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    输入一张收据 + 参与者 + 策略，返回每人应付多少 + 可解释明细。
    需登录；结果会记录到当前用户名下。
    """
    try:
        result = compute(req.receipt, req.participants, req.method)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.save_split(user["id"], None, req.method, json.dumps(result["shares"]))
    result["saved"] = True
    return result


# ---------------------------------------------------------------------------
# 路由 2：结算（债务最小化）
# ---------------------------------------------------------------------------
@router.post("/settle")
def post_settle(
    req: SettleRequest,
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """输入各人份额 + 垫付者 + 总额，返回最少笔数的转账方案。需登录。"""
    return settle(req.shares, req.paid_by, req.total)


# ---------------------------------------------------------------------------
# 路由 3：OCR —— 上传收据图片，返回结构化 Receipt
# ---------------------------------------------------------------------------
@router.post("/ocr")
async def post_ocr(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> Receipt:
    """上传一张收据图片，返回抽取出的 Receipt（items/tax/paid_by）。需登录。"""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件（content-type 须以 image/ 开头）")
    image_bytes = await file.read()
    try:
        return extract_receipt(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# 路由 4：Scan —— 一步到位：上传图片 + 参与者，直接给出分账结果
# ---------------------------------------------------------------------------
@router.post("/scan")
async def post_scan(
    file: UploadFile = File(...),
    participants: str = Form(..., description="参与者 JSON 数组，如 [{'id':'u1','name':'Alice'}]"),
    method: str = Form("equal", description="equal | per_item | proportional | weighted"),
    paid_by: str = Form("", description="垫付人 id；未指定时默认用 participants 第一个"),
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    便捷端点：图片进、分账结果出。需登录，且会把收据与分账落库。
    participants 以表单字段（JSON 字符串）传入，method 默认 equal。
    """
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")

    # 1) 解析参与者
    try:
        parsed = json.loads(participants)
        people = [Participant.model_validate(p) for p in parsed]
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"participants 解析失败: {e}")

    # 2) 图片 -> Receipt
    image_bytes = await file.read()
    try:
        receipt = extract_receipt(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 垫付人优先级：用户显式选择 > VLM 识别结果 > 第一个参与者。
    # 用户在下拉框里的选择是显式意图，必须压在模型推测之上；
    # 同时用 valid_ids 白名单兜底，防止 VLM 返回人名（如 "Alice"）而非 id 时算出幽灵份额。
    valid_ids = {p.id for p in people}
    explicit = (paid_by or "").strip()
    if explicit and explicit in valid_ids:
        receipt.paid_by = explicit
    elif receipt.paid_by not in valid_ids:
        receipt.paid_by = people[0].id if people else "u1"

    # 3) Receipt -> 分账 + 落库（与 /confirm 共用同一段逻辑）
    try:
        return _split_and_persist(user, receipt, people, method, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# 路由 5：Confirm —— 两步式流程第二步：不带图，提交已分配好的收据
# ---------------------------------------------------------------------------
@router.post("/confirm")
def post_confirm(
    req: ConfirmRequest,
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    前端先用 /ocr 识别出菜品，用户在界面上勾选「谁点了哪道菜」后，
    把填好 assigned_to 的收据回传至此，直接结算并落库。

    与 /scan 的区别：不带图片、不重复调用 VLM；
    与 /split 的区别：会把收据一起存下来（/split 落库时 receipt_id 为 NULL），
    因此分配结果可在「历史记录」里追溯。
    """
    try:
        return _split_and_persist(
            user, req.receipt, req.participants, req.method, "手动分配"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# 路由 5：历史 —— 当前用户自己的收据 + 分账
# ---------------------------------------------------------------------------
@router.get("/history")
def get_history(user: dict = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """返回当前登录用户最近的收据与分账记录。"""
    return db.list_history(user["id"])
