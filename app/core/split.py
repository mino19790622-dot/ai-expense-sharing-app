from typing import List, Dict, Any
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# 1. 数据模型：描述一张收据长什么样（Stage 3 接 API 时直接白赚）
# ---------------------------------------------------------------------------
class LineItem(BaseModel):
    description: str
    amount: float
    assigned_to: List[str] = []   # 谁点了它；空 = 所有人平摊


class Participant(BaseModel):
    id: str
    name: str
    weight: float = 1.0           # 给 weighted 策略用


class Receipt(BaseModel):
    items: List[LineItem]
    tax: float = 0.0
    paid_by: str                  # 谁先垫的钱


# ---------------------------------------------------------------------------
# 2. 浮点安全：一切金额内部用「分」(int) 计算，最后才转回元(float)
#    原因：0.1 + 0.2 != 0.3，直接拿浮点求和会对不上账。
# ---------------------------------------------------------------------------
def to_cents(x: float) -> int:
    return int(round(x * 100))


def _responsible(item: LineItem, participant_ids: List[str]) -> List[str]:
    """谁该为这笔 item 负责：assigned_to 非空取其值，为空则所有人平摊。"""
    return item.assigned_to if item.assigned_to else participant_ids


# ---------------------------------------------------------------------------
# 3. 核心：把一张收据按某种策略拆成「每人应付多少」
# ---------------------------------------------------------------------------
def compute(receipt: Receipt, participants: List[Participant], method: str) -> Dict[str, Any]:
    participant_ids = [p.id for p in participants]
    n = len(participant_ids)

    # 全部转成「分」，后续只用整数运算
    item_cents = [to_cents(it.amount) for it in receipt.items]
    tax_cents = to_cents(receipt.tax)
    total_cents = sum(item_cents) + tax_cents

    # 每个 item 的负责者列表（提前算好，下面四种策略共用）
    responsible = [_responsible(it, participant_ids) for it in receipt.items]

    # 每人应付（分），初始化为 0
    shares_cents: Dict[str, int] = {pid: 0 for pid in participant_ids}

    # ---- 四种策略，仅这一段的「权重怎么定」不同 ----
    if method == "equal":
        base = total_cents // n
        for pid in participant_ids:
            shares_cents[pid] = base

    elif method == "per_item":
        # 每个 item 由它的负责者平摊；税作为公共成本按人头均摊给所有人
        for cents, resp in zip(item_cents, responsible):
            if resp:
                per = cents // len(resp)
                for pid in resp:
                    shares_cents[pid] += per
        tax_per = tax_cents // n
        for pid in participant_ids:
            shares_cents[pid] += tax_per

    elif method == "proportional":
        # 每人『消费额』= 其负责 item 金额之和；税也按同一占比摊
        consumed = {pid: 0 for pid in participant_ids}
        for cents, resp in zip(item_cents, responsible):
            if resp:
                per = cents // len(resp)
                for pid in resp:
                    consumed[pid] += per
        total_consumed = sum(consumed.values())
        if total_consumed == 0:           # 极端兜底：没人消费则退化为 equal
            base = total_cents // n
            for pid in participant_ids:
                shares_cents[pid] = base
        else:
            for pid in participant_ids:
                shares_cents[pid] = total_cents * consumed[pid] // total_consumed

    elif method == "weighted":
        total_weight = sum(p.weight for p in participants)
        if total_weight == 0:            # 兜底：权重全 0 则退化为 equal
            base = total_cents // n
            for pid in participant_ids:
                shares_cents[pid] = base
        else:
            for p in participants:
                shares_cents[p.id] = total_cents * p.weight // total_weight

    else:
        raise ValueError(f"Unknown split method: {method}")

    # ---- 余数补偿：整数除法会丢几分，把差额塞给垫付人，保证守恒 ----
    remainder = total_cents - sum(shares_cents.values())
    if remainder != 0:
        target = receipt.paid_by if receipt.paid_by in shares_cents else participant_ids[0]
        shares_cents[target] += remainder

    # ---- 转回元(float, 2位) + 拼人类可读明细 ----
    shares = {pid: round(c / 100, 2) for pid, c in shares_cents.items()}
    explanation = [f"{p.name}（{p.id}）应付 ¥{shares[p.id]:.2f}" for p in participants]

    return {
        "shares": shares,
        "explanation": explanation,
        "total": round(total_cents / 100, 2),
        "paid_by": receipt.paid_by,
    }
