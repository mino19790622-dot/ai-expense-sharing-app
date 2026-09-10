
from app.core.split import compute, LineItem, Participant, Receipt

def test_equal():
    r = Receipt(items=[LineItem(description="x", amount=100)],
                tax=0, paid_by="u1")
    parts = [Participant(id="u1", name="A"),
             Participant(id="u2", name="B"),
             Participant(id="u3", name="C"),
             Participant(id="u4", name="D")]
    out = compute(r, parts, "equal")
    assert out["shares"] == {"u1":25,"u2":25,"u3":25,"u4":25}

def test_per_item_assigned():
    r = Receipt(items=[
        LineItem(description="披萨", amount=30, assigned_to=["u1","u2"]),
        LineItem(description="可乐", amount=20, assigned_to=["u3"]),
    ], tax=0, paid_by="u1")
    parts = [Participant(id="u1",name="A"),Participant(id="u2",name="B"),
             Participant(id="u3",name="C")]
    out = compute(r, parts, "per_item")
    # 披萨 30 由 u1,u2 平摊 → 各15；可乐 20 全 u3
    assert out["shares"] == {"u1":15,"u2":15,"u3":20}

def test_per_item_empty_assigned_means_all():
    # assigned_to 为空 = 大家平摊
    r = Receipt(items=[LineItem(description="餐", amount=60, assigned_to=[])],
                tax=0, paid_by="u1")
    parts = [Participant(id="u1",name="A"),Participant(id="u2",name="B"),
             Participant(id="u3",name="C")]
    out = compute(r, parts, "per_item")
    assert out["shares"] == {"u1":20,"u2":20,"u3":20}

def test_weighted():
    r = Receipt(items=[LineItem(description="x", amount=100)],
                tax=0, paid_by="u1")
    parts = [Participant(id="u1",name="A",weight=1.0),
             Participant(id="u2",name="B",weight=0.5)]  # B 是半份
    out = compute(r, parts, "weighted")
    # 总权重 1.5，每权重 66.67；u1=66.67, u2=33.33
    assert abs(out["shares"]["u1"] - 66.67) < 0.01
    assert abs(out["shares"]["u2"] - 33.33) < 0.01

def test_total_conserved():
    # 守恒：所有 shares 之和 == 总消费
    r = Receipt(items=[LineItem(description="a", amount=33.33),
                       LineItem(description="b", amount=33.33),
                       LineItem(description="c", amount=33.34)],
                tax=0.01, paid_by="u1")
    parts = [Participant(id="u1",name="A"),Participant(id="u2",name="B")]
    out = compute(r, parts, "equal")
    assert abs(sum(out["shares"].values()) - 100.01) < 0.001

