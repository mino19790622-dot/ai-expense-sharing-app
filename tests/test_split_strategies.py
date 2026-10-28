"""Coverage for the split paths that had none.

``test_split.py`` covers ``equal`` / ``per_item`` / ``weighted`` and the
conservation invariant. Left uncovered were:

  * ``proportional`` — the whole strategy, including the fact that tax follows
    consumption rather than headcount (which is the only thing that makes it
    different from ``per_item``);
  * both degenerate-input fallbacks (nobody consumed, all weights zero);
  * the unknown-method guard;
  * where the integer-division remainder is parked;
  * the remainder fallback for a ghost ``paid_by`` (not in ``participants``),
    which parks the cents on ``participants[0]`` instead;
  * a participant who consumed nothing under ``proportional`` — they pay zero,
    tax included, which is where this strategy diverges from ``per_item``.
"""

import pytest

from app.core.split import LineItem, Participant, Receipt, compute, to_cents


def _parts(*ids):
    return [Participant(id=i, name=i.upper()) for i in ids]


def _two_person_receipt():
    """u1 consumes 10, u2 consumes 30, plus a 20 tax — 60 total."""
    return Receipt(
        items=[
            LineItem(description="咖啡", amount=10, assigned_to=["u1"]),
            LineItem(description="牛排", amount=30, assigned_to=["u2"]),
        ],
        tax=20,
        paid_by="u1",
    )


# ------------------------------------------------------------- proportional
def test_proportional_spreads_tax_by_consumption_not_headcount():
    out = compute(_two_person_receipt(), _parts("u1", "u2"), "proportional")
    # consumption ratio 10:30 -> 60 total split 1:3 -> 15 / 45
    assert out["shares"] == {"u1": 15.0, "u2": 45.0}
    assert out["total"] == 60.0


def test_proportional_is_not_per_item_when_tax_is_large():
    """Guards the strategy against silently collapsing into per_item."""
    receipt = _two_person_receipt()
    prop = compute(receipt, _parts("u1", "u2"), "proportional")["shares"]
    per_item = compute(receipt, _parts("u1", "u2"), "per_item")["shares"]
    # per_item splits the tax evenly (1000 each), proportional splits it 1:3
    assert per_item == {"u1": 20.0, "u2": 40.0}
    assert prop != per_item


def test_proportional_conserves_the_total():
    out = compute(_two_person_receipt(), _parts("u1", "u2"), "proportional")
    assert round(sum(out["shares"].values()), 2) == out["total"]


def test_proportional_falls_back_to_equal_when_nobody_consumed():
    receipt = Receipt(items=[LineItem(description="空单", amount=0)], tax=10, paid_by="u1")
    out = compute(receipt, _parts("u1", "u2"), "proportional")
    assert out["shares"] == {"u1": 5.0, "u2": 5.0}


# ----------------------------------------------------------------- fallbacks
def test_weighted_falls_back_to_equal_when_all_weights_are_zero():
    receipt = Receipt(items=[LineItem(description="x", amount=10)], tax=0, paid_by="u1")
    parts = [
        Participant(id="u1", name="A", weight=0.0),
        Participant(id="u2", name="B", weight=0.0),
    ]
    assert compute(receipt, parts, "weighted")["shares"] == {"u1": 5.0, "u2": 5.0}


def test_unknown_method_raises():
    receipt = Receipt(items=[LineItem(description="x", amount=10)], tax=0, paid_by="u1")
    with pytest.raises(ValueError, match="Unknown split method"):
        compute(receipt, _parts("u1"), "bogus")


# ------------------------------------------------------- remainder / rounding
def test_remainder_cents_land_on_the_payer():
    receipt = Receipt(items=[LineItem(description="x", amount=10)], tax=0, paid_by="u2")
    out = compute(receipt, _parts("u1", "u2", "u3"), "equal")
    # 1000 // 3 = 333 each = 999, so exactly 1 cent goes to the payer (u2)
    assert out["shares"] == {"u1": 3.33, "u2": 3.34, "u3": 3.33}
    assert round(sum(out["shares"].values()), 2) == 10.0


def test_to_cents_rounds_to_whole_cents():
    assert to_cents(19.99) == 1999
    assert to_cents(0.1) == 10
    assert to_cents(0.0) == 0


def test_remainder_falls_back_to_first_participant_when_payer_is_ghost():
    """``paid_by`` outside ``participants`` must still conserve the total.

    ``compute`` parks the integer-division remainder on the payer, but only if
    the payer is actually in ``shares_cents``; otherwise it falls back to
    ``participant_ids[0]``.  The API layer rewrites ghost payers before calling
    in (see ``test_scan_falls_back_to_first_participant_when_paid_by_is_ghost``),
    so this branch is only reachable through the core function directly.
    """
    receipt = Receipt(items=[LineItem(description="x", amount=10)], tax=0, paid_by="ghost")
    out = compute(receipt, _parts("u1", "u2", "u3"), "equal")
    # 1000 // 3 = 333 each = 999, the stray cent lands on u1, not on "ghost"
    assert out["shares"] == {"u1": 3.34, "u2": 3.33, "u3": 3.33}
    assert "ghost" not in out["shares"]
    assert out["paid_by"] == "ghost"  # echoed back untouched, never sanitised here
    assert round(sum(out["shares"].values()), 2) == out["total"] == 10.0


def test_proportional_charges_a_non_consumer_nothing_not_even_tax():
    """Under ``proportional`` a participant who ordered nothing pays zero.

    ``per_item`` would still charge them a headcount share of the tax; this
    test pins that ``proportional`` does not.
    """
    receipt = Receipt(
        items=[
            LineItem(description="咖啡", amount=10, assigned_to=["u1"]),
            LineItem(description="牛排", amount=30, assigned_to=["u2"]),
        ],
        tax=20,
        paid_by="u1",
    )
    parts = _parts("u1", "u2", "u3")
    prop = compute(receipt, parts, "proportional")
    assert prop["shares"] == {"u1": 15.0, "u2": 45.0, "u3": 0.0}
    assert compute(receipt, parts, "per_item")["shares"]["u3"] > 0
    assert round(sum(prop["shares"].values()), 2) == prop["total"] == 60.0

