"""Overdue-invoice aging and an explainable dunning cadence.

Given invoices (amount in whole cents, a due date, and any payments already
applied), chaseledger computes the outstanding balance, assigns an aging bucket,
and proposes the next chase action with a reason and a suggested follow-up date.

Everything is deterministic integer-cent math — no floating point money — and
every decision carries a human-readable explanation so the plan can be audited.
"""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass, field
from enum import Enum

DAY = dt.timedelta(days=1)

# (upper bound of days overdue inclusive, bucket name), checked in order.
AGING_BUCKETS = (
    (0, "current"),
    (30, "1-30"),
    (61, "31-60"),
    (90, "61-90"),
    (10**9, "90+"),
)


class Action(Enum):
    NONE = "none"
    FRIENDLY_REMINDER = "friendly-reminder"
    SECOND_REMINDER = "second-reminder"
    FINAL_NOTICE = "final-notice"
    ESCALATE = "escalate-to-collections"


@dataclass
class Invoice:
    invoice_id: str
    customer: str
    amount_cents: int
    due_date: dt.date
    paid_cents: int = 0

    @property
    def balance_cents(self) -> int:
        return max(0, self.amount_cents - self.paid_cents)

    @property
    def is_paid(self) -> bool:
        return self.balance_cents == 0


@dataclass
class ChasePlan:
    invoice: Invoice
    days_overdue: int
    bucket: str
    action: Action
    reason: str
    next_follow_up: dt.date | None


def aging_bucket(days_overdue: int) -> str:
    """Map a days-overdue count to a named aging bucket."""
    for upper, name in AGING_BUCKETS:
        if days_overdue <= upper:
            return name
    return "90+"


def days_overdue(invoice: Invoice, as_of: dt.date) -> int:
    if invoice.is_paid:
        return 0
    return max(0, (as_of - invoice.due_date).days)


# Dunning cadence: (min_days_overdue, action, follow_up_days, reason).
# First matching rung wins. Escalation is reserved for large, very old debts.
_CADENCE = (
    (1, Action.FRIENDLY_REMINDER, 7, "just passed due date — polite nudge"),
    (15, Action.SECOND_REMINDER, 10, "over two weeks — firmer reminder"),
    (31, Action.FINAL_NOTICE, 14, "over a month — final notice before escalation"),
    (61, Action.ESCALATE, 30, "over two months — refer to collections"),
)


def plan_chase(invoice: Invoice, as_of: dt.date, escalation_balance_cents: int = 50000) -> ChasePlan:
    """Decide the next chase action for one invoice as of ``as_of``."""
    overdue = days_overdue(invoice, as_of)
    bucket = aging_bucket(overdue)

    if invoice.is_paid:
        return ChasePlan(invoice, 0, "current", Action.NONE,
                         "settled in full — no action", None)

    for min_days, action, follow_days, reason in reversed(_CADENCE):
        if overdue >= min_days:
            # Only escalate genuinely large balances; smaller ones get a final notice.
            if action is Action.ESCALATE and invoice.balance_cents < escalation_balance_cents:
                action = Action.FINAL_NOTICE
                reason = "over two months but small balance — hold at final notice"
            return ChasePlan(
                invoice, overdue, bucket, action, reason,
                as_of + follow_days * DAY,
            )

    # Not yet overdue.
    return ChasePlan(invoice, overdue, bucket, Action.NONE,
                     "not yet due", None)


def plan_all(invoices: list[Invoice], as_of: dt.date, **kwargs) -> list[ChasePlan]:
    return [plan_chase(inv, as_of, **kwargs) for inv in invoices]


@dataclass
class Summary:
    total_balance_cents: int
    by_bucket: dict[str, int] = field(default_factory=dict)
    by_action: dict[str, int] = field(default_factory=dict)


def summarize(plans: list[ChasePlan]) -> Summary:
    total = 0
    by_bucket: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for p in plans:
        bal = p.invoice.balance_cents
        total += bal
        by_bucket[p.bucket] = by_bucket.get(p.bucket, 0) + 1
        by_action[p.action.value] = by_action.get(p.action.value, 0) + 1
    return Summary(total_balance_cents=total, by_bucket=by_bucket, by_action=by_action)


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100}.{cents % 100:02d}"


def render_plan(plans: list[ChasePlan]) -> str:
    lines = []
    for p in sorted(plans, key=lambda x: (-x.days_overdue, x.invoice.invoice_id)):
        follow = p.next_follow_up.isoformat() if p.next_follow_up else "-"
        lines.append(
            f"{p.invoice.invoice_id:<10} {p.invoice.customer:<16} "
            f"{money(p.invoice.balance_cents):>10}  {p.days_overdue:>3}d "
            f"[{p.bucket:<5}] {p.action.value:<22} next:{follow}  {p.reason}"
        )
    return "\n".join(lines) if lines else "(no invoices)"


def load_csv(path: str) -> list[Invoice]:
    """Load invoices from a CSV with columns:
    invoice_id,customer,amount_cents,due_date[,paid_cents]

    ``amount_cents``/``paid_cents`` are integers; ``due_date`` is ISO ``YYYY-MM-DD``.
    """
    invoices: list[Invoice] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            invoices.append(
                Invoice(
                    invoice_id=row["invoice_id"].strip(),
                    customer=row["customer"].strip(),
                    amount_cents=int(row["amount_cents"]),
                    due_date=dt.date.fromisoformat(row["due_date"].strip()),
                    paid_cents=int(row.get("paid_cents") or 0),
                )
            )
    return invoices
