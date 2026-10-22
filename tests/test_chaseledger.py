import datetime as dt

from chaseledger.chaseledger import (
    Action,
    Invoice,
    aging_bucket,
    days_overdue,
    money,
    plan_chase,
    render_plan,
    summarize,
)

AS_OF = dt.date(2026, 10, 29)


def _inv(days_overdue, amount=10000, paid=0, iid="INV-1", customer="Acme"):
    return Invoice(iid, customer, amount, AS_OF - dt.timedelta(days=days_overdue), paid)


def test_balance_and_paid():
    inv = _inv(10, amount=5000, paid=2000)
    assert inv.balance_cents == 3000
    assert not inv.is_paid
    assert _inv(0, amount=100, paid=100).is_paid


def test_aging_buckets():
    assert aging_bucket(0) == "current"
    assert aging_bucket(15) == "1-30"
    assert aging_bucket(45) == "31-60"
    assert aging_bucket(75) == "61-90"
    assert aging_bucket(120) == "90+"


def test_days_overdue():
    assert days_overdue(_inv(20), AS_OF) == 20
    assert days_overdue(_inv(0, amount=10, paid=10), AS_OF) == 0  # paid -> not overdue


def test_not_yet_due():
    future = Invoice("INV-0", "Zed", 1000, AS_OF + dt.timedelta(days=5))
    p = plan_chase(future, AS_OF)
    assert p.action is Action.NONE and p.next_follow_up is None


def test_escalation_only_for_large_balances():
    large = plan_chase(_inv(70, amount=90000), AS_OF)
    small = plan_chase(_inv(70, amount=1000), AS_OF)
    assert large.action is Action.ESCALATE
    assert small.action is Action.FINAL_NOTICE  # below default 50000 threshold


def test_cadence_escalates_with_age():
    assert plan_chase(_inv(3), AS_OF).action is Action.FRIENDLY_REMINDER
    assert plan_chase(_inv(20), AS_OF).action is Action.SECOND_REMINDER
    assert plan_chase(_inv(45), AS_OF).action is Action.FINAL_NOTICE


def test_paid_invoice_no_action():
    p = plan_chase(_inv(40, amount=1000, paid=1000), AS_OF)
    assert p.action is Action.NONE and p.days_overdue == 0


def test_money_formatting():
    assert money(118800) == "$1188.00"
    assert money(5) == "$0.05"
    assert money(-250) == "-$2.50"


def test_summarize_and_render():
    plans = [plan_chase(_inv(3, iid="A"), AS_OF), plan_chase(_inv(70, amount=90000, iid="B"), AS_OF)]
    s = summarize(plans)
    assert s.total_balance_cents == 100000  # 10000 (A) + 90000 (B)
    assert s.by_action["escalate-to-collections"] == 1
    text = render_plan(plans)
    assert "INV" not in text or "A" in text
    assert "escalate-to-collections" in text
