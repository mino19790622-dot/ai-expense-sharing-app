from app.core.debt import _min_cash_flow, naive_settle, settle


def test_simple_two_people():
    # u1 垫付 50，两人平摊各 25
    shares = {"u1": 25.0, "u2": 25.0}
    out = settle(shares, paid_by="u1", total=50.0)
    # u2 欠 u1 25
    assert out["transfers"] == [{"from": "u2", "to": "u1", "amount": 25.0}]
    assert out["num_transactions"] == 1


def test_creditor_receives_from_two_debtors():
    # u1 垫付 60；u2 应摊 40、u3 应摊 20
    shares = {"u1": 40.0, "u2": 40.0, "u3": 20.0}
    out = settle(shares, paid_by="u1", total=100.0)
    # 最少笔数应为 2：u2->u1 40, u3->u1 20
    assert out["num_transactions"] == 2
    total_paid_to_u1 = sum(t["amount"] for t in out["transfers"] if t["to"] == "u1")
    assert total_paid_to_u1 == 60.0


def test_two_party_cases_match_naive_count():
    # 说明：这两个例子**并不能**证明「贪心比朴素少笔数」——两边的笔数其实相等。
    # 在 settle() 的模型里，只有垫付者付过钱，所以除他以外每个人的净余额都 <= 0，
    # 债权人有且只有垫付者一个；单一债权人下贪心就是把每个债务人依次还清，
    # 笔数必然等于 naive_settle 的「人数-1」。真正能看到贪心优势的是 _min_cash_flow
    # 的多债权人输入（见下面两个用例），那不是 settle() 能构造出来的场景。
    shares = {"u1": 50.0, "u2": 50.0, "u3": 50.0}
    out = settle(shares, paid_by="u1", total=150.0)
    # 贪心：2 笔（u2->u1 50, u3->u1 50）；朴素也是 2 笔，相等
    assert out["num_transactions"] == 2
    assert out["num_transactions"] == len(naive_settle(shares, "u1"))
    # 换个分摊结构：u1 垫 100，u2 摊 40，u3 摊 20
    shares2 = {"u1": 40.0, "u2": 40.0, "u3": 20.0}
    out2 = settle(shares2, paid_by="u1", total=100.0)
    assert out2["num_transactions"] == len(naive_settle(shares2, "u1"))


def test_settle_has_a_single_creditor_so_counts_never_beat_naive():
    # 钉住上面那条结论：settle() 里非垫付者的余额一律 <= 0（不可能成为债权人），
    # 故最少笔数恒等于 naive_settle 的笔数。含三人分摊除不尽的用例。
    for shares, total in [
        ({"u1": 18.33, "u2": 18.33, "u3": 23.34}, 60.0),
        ({"u1": 3.34, "u2": 3.33, "u3": 3.33}, 10.0),
        ({"u1": 0.0, "u2": 5.0}, 5.0),
    ]:
        out = settle(shares, paid_by="u1", total=total)
        assert all(b <= 0 for p, b in out["balances"].items() if p != "u1")
        assert out["num_transactions"] == len(naive_settle(shares, "u1"))


def test_balances_sum_to_zero():
    shares = {"u1": 18.33, "u2": 18.33, "u3": 23.34}
    out = settle(shares, paid_by="u1", total=60.0)
    # 所有余额之和应 ≈ 0
    assert abs(sum(out["balances"].values())) < 0.01


def test_three_person_cycle_minimized():
    # 构造需要「三角对冲」才能最小化的例子：
    # 余额：u1 +30（应收）, u2 -10, u3 -20
    # 贪心：u2->u1 10, u3->u1 20 → 2 笔
    shares = {"u1": 0.0, "u2": 10.0, "u3": 20.0}  # 假设 u1 没摊(被豁免)，u2/u3 摊
    # 但 paid_by 必须是其一；这里让 u1 垫付 total=30
    out = settle(shares, paid_by="u1", total=30.0)
    assert out["num_transactions"] == 2
    # 校验：每笔 from 的金额都流向了 u1
    for t in out["transfers"]:
        assert t["to"] == "u1"
    assert sum(t["amount"] for t in out["transfers"]) == 30.0


def test_min_cash_flow_chains_two_debtors_into_two_creditors():
    # 直接测贪心核心（输入输出都是「分」）：欠得最多的 a 先配该收最多的 c，
    # 归零后再让 b 依次与 c、d 配对 ⇒ 恰好 3 笔
    out = _min_cash_flow({"a": -300, "b": -200, "c": 400, "d": 100})
    assert out == [
        {"from": "a", "to": "c", "amount_cents": 300},
        {"from": "b", "to": "c", "amount_cents": 100},
        {"from": "b", "to": "d", "amount_cents": 100},
    ]


def test_min_cash_flow_needs_both_sides_and_keeps_cents():
    # 缺少债务人（全为 0）或缺少债权人（空）时都不该产生转账
    assert _min_cash_flow({}) == []
    assert _min_cash_flow({"a": 0, "b": 0}) == []
    # 金额一律用整数「分」，且转出总额 == 债权总额（钱不会凭空消失）
    out = _min_cash_flow({"a": -300, "b": -200, "c": 400, "d": 100})
    assert all(isinstance(t["amount_cents"], int) for t in out)
    assert sum(t["amount_cents"] for t in out) == 500
