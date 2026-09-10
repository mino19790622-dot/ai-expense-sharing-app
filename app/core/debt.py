from typing import Dict, Any, List
from app.core.split import to_cents


# ---------------------------------------------------------------------------
# 1. 问题建模：什么是「债务最小化」
# ---------------------------------------------------------------------------
# compute() 只回答「每人该付多少（share）」，但现实里是某一个人（paid_by）
# 先把整单垫付了。于是每个人有个「净余额」：
#
#     balance[p] = 实际已付(p) - 应摊份额(p)
#
#   - balance > 0  → 多付了，应该被还钱（债权人 / creditor）
#   - balance < 0  → 少付了，应该补钱（债务人 / debtor）
#   - 所有人 balance 之和 = 0（钱不会凭空消失）
#
# 目标：用「最少笔数的转账」让所有 balance 归零。
# 这是经典贪心算法「最小现金流 / minimum cash flow」，也是面试高频白板题。


# ---------------------------------------------------------------------------
# 2. 核心算法：贪心最小现金流（输入/输出都用「分」整数，避免浮点）
# ---------------------------------------------------------------------------
def _min_cash_flow(balances_cents: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    贪心还原最小转账笔数。
    思路：每轮取「欠得最多的债务人」和「该收最多的债权人」配对，
          还一笔能还多少还多少，直到其中一方归零，再换下一对。
    数学上可证明该贪心得到的是最优（最少笔数）解。
    """
    # 债务人按「欠得少→多」排（先处理欠得多的）；债权人按「该收多→少」排
    debtors = sorted([(p, b) for p, b in balances_cents.items() if b < 0], key=lambda x: x[1])
    creditors = sorted([(p, b) for p, b in balances_cents.items() if b > 0], key=lambda x: -x[1])

    transfers: List[Dict[str, Any]] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        d_pid, d_amt = debtors[i]   # d_amt < 0
        c_pid, c_amt = creditors[j] # c_amt > 0
        # 这一笔最多还 min(还欠的, 该收的)
        amt = min(-d_amt, c_amt)
        transfers.append({"from": d_pid, "to": c_pid, "amount_cents": amt})

        # 更新两边余额
        debtors[i] = (d_pid, d_amt + amt)
        creditors[j] = (c_pid, c_amt - amt)

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers


# ---------------------------------------------------------------------------
# 3. 对外接口：从 shares + paid_by + total 算结算方案
# ---------------------------------------------------------------------------
def settle(shares: Dict[str, float], paid_by: str, total: float) -> Dict[str, Any]:
    """
    参数:
        shares:  compute() 的返回值 {"shares": {pid: 元}} 里的那份 dict
                 e.g. {"u1": 18.33, "u2": 18.33, "u3": 23.33}
        paid_by: 谁先垫付了整单（compute 的 paid_by）
        total:   整单总额（应收据算，或 compute 的 "total"）
    返回:
        {
          "transfers": [{"from": pid, "to": pid, "amount": 元}, ...],  # 最少笔数
          "balances":  {pid: 元},     # 每个人的净余额（>0 应收，<0 应付）
          "num_transactions": int,    # 实际转账笔数
        }
    """
    all_pids = list(shares.keys())

    # 每个人实际已付：垫付者付了 total，其余人付 0
    paid = {p: (total if p == paid_by else 0.0) for p in all_pids}

    # 净余额（元）→ 转「分」整数做精确运算
    balances_yuan = {p: round(paid[p] - shares[p], 2) for p in all_pids}
    balances_cents = {p: to_cents(b) for p, b in balances_yuan.items()}

    # 跑贪心
    transfers_cents = _min_cash_flow(balances_cents)

    # 转回元
    transfers = [
        {"from": t["from"], "to": t["to"], "amount": round(t["amount_cents"] / 100, 2)}
        for t in transfers_cents
    ]

    return {
        "transfers": transfers,
        "balances": balances_yuan,
        "num_transactions": len(transfers),
    }


# ---------------------------------------------------------------------------
# 4. 对比用：朴素结算（每个人直接还垫付者）—— 用来体现「最小化」的价值
# ---------------------------------------------------------------------------
def naive_settle(shares: Dict[str, float], paid_by: str) -> List[Dict[str, Any]]:
    """不做图优化，每人把自己份额直接转给垫付者。笔数 = 人数-1。"""
    out = []
    for pid, amt in shares.items():
        if pid != paid_by and amt > 0:
            out.append({"from": pid, "to": paid_by, "amount": round(amt, 2)})
    return out
