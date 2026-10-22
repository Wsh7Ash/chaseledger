"""Command-line interface for chaseledger."""
from __future__ import annotations

import argparse
import datetime as dt

from .chaseledger import load_csv, money, plan_all, render_plan, summarize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chaseledger",
        description="Age overdue invoices and produce an explainable chase plan.",
    )
    parser.add_argument("csv", help="CSV of invoices (invoice_id,customer,amount_cents,due_date[,paid_cents])")
    parser.add_argument(
        "--as-of", default=None,
        help="ISO date to evaluate as of (default: today)",
    )
    parser.add_argument(
        "--escalation-balance", type=int, default=50000,
        help="Minimum balance in cents to escalate to collections (default 50000)",
    )
    args = parser.parse_args(argv)

    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()
    invoices = load_csv(args.csv)
    plans = plan_all(invoices, as_of, escalation_balance_cents=args.escalation_balance)

    print(f"Chase plan as of {as_of.isoformat()}")
    print(render_plan(plans))

    s = summarize(plans)
    print()
    print(f"Total outstanding: {money(s.total_balance_cents)}")
    print("By bucket:  " + ", ".join(f"{k}={v}" for k, v in sorted(s.by_bucket.items())))
    print("By action:  " + ", ".join(f"{k}={v}" for k, v in sorted(s.by_action.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
