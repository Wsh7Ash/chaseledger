# chaseledger

Turn a pile of overdue invoices into an explainable chase plan. `chaseledger`
ages each invoice into a bucket and proposes the next dunning action — a polite
nudge, a firmer reminder, a final notice, or a referral to collections — each
with a reason and a suggested follow-up date.

Money math is exact integer cents (no floating point), and every decision
carries a human-readable explanation so the plan is auditable.

## Aging buckets

| Bucket    | Days overdue |
|-----------|--------------|
| `current` | 0            |
| `1-30`    | 1–30         |
| `31-60`   | 31–60        |
| `61-90`   | 61–90        |
| `90+`     | 91+          |

## Dunning cadence

| Days overdue | Action                  | Follow-up |
|--------------|-------------------------|-----------|
| 1+           | friendly-reminder       | 7 days    |
| 15+          | second-reminder         | 10 days   |
| 31+          | final-notice            | 14 days   |
| 61+          | escalate-to-collections | 30 days   |

Escalation is reserved for balances at or above `--escalation-balance` (default
50000 cents). Smaller, very old debts are held at a final notice. Paid invoices
and not-yet-due invoices get no action.

## Install

```
pip install -e .
```

## Usage

```
chaseledger invoices.csv --as-of 2026-10-29
```

CSV columns: `invoice_id,customer,amount_cents,due_date[,paid_cents]` with ISO
dates. Prints one line per invoice plus a bucket/action summary.

## Python API

```python
import datetime as dt
from chaseledger import Invoice, plan_chase, summarize

inv = Invoice("INV-1", "Acme", 250000, dt.date(2026, 9, 1))
plan = plan_chase(inv, dt.date(2026, 10, 29))
print(plan.action, plan.reason, plan.next_follow_up)
```

## License

MIT
