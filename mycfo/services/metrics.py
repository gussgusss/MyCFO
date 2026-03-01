from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from ..models import Transaction, Workspace


def compute_metrics(*, workspace: Workspace, transactions: list[Transaction], as_of: date) -> dict:
    end_dt = datetime.combine(as_of, time.max, tzinfo=timezone.utc)
    start_dt = end_dt - timedelta(days=30)
    window_transactions = [txn for txn in transactions if start_dt <= _coerce_utc(txn.occurred_at) <= end_dt]
    previous_start = start_dt - timedelta(days=30)
    previous_transactions = [txn for txn in transactions if previous_start <= _coerce_utc(txn.occurred_at) < start_dt]

    gross_revenue = sum(
        txn.amount_cents for txn in window_transactions if txn.type == "revenue" and txn.subtype != "refund"
    )
    refunds = sum(txn.amount_cents for txn in window_transactions if txn.subtype == "refund")
    net_revenue = gross_revenue + refunds
    recurring_expenses = sum(
        txn.amount_cents for txn in window_transactions
        if txn.type == "expense" and txn.subtype == "recurring_expense"
    )
    one_time_expenses = sum(
        txn.amount_cents for txn in window_transactions
        if txn.type == "expense" and txn.subtype == "one_time_expense"
    )
    total_expenses = recurring_expenses + one_time_expenses
    burn = total_expenses - net_revenue
    recurring_burn = recurring_expenses - net_revenue

    recurring_revenue = sum(
        txn.amount_cents
        for txn in window_transactions
        if txn.type == "revenue" and txn.subtype in {"subscription_invoice", "recurring_revenue"}
    )
    arpa = int(recurring_revenue / max(_distinct_customers(window_transactions), 1))
    cash_on_hand = workspace.cash_on_hand_cents
    runway_months = round(cash_on_hand / recurring_burn, 2) if cash_on_hand is not None and recurring_burn > 0 else None

    warnings = []
    if cash_on_hand is None:
        warnings.append(
            {"code": "missing_cash", "message": "cash_on_hand_cents not configured on workspace; runway is null."}
        )
    if not any(txn.subtype == "subscription_event" for txn in transactions):
        warnings.append(
            {
                "code": "churn_unavailable",
                "message": "No subscription lifecycle data ingested; churn metrics are approximated as null.",
            }
        )

    previous_mrr = sum(
        txn.amount_cents
        for txn in previous_transactions
        if txn.type == "revenue" and txn.subtype in {"subscription_invoice", "recurring_revenue"}
    )
    current_mrr = recurring_revenue
    refunds_prev = sum(txn.amount_cents for txn in previous_transactions if txn.subtype == "refund")

    return {
        "as_of": as_of.isoformat(),
        "currency": _currency_for_transactions(transactions),
        "mrr_cents": current_mrr,
        "arr_cents": current_mrr * 12,
        "gross_revenue_cents_30d": gross_revenue,
        "refunds_cents_30d": refunds,
        "net_revenue_cents_30d": net_revenue,
        "burn_cents_30d": burn,
        "recurring_burn_cents_30d": recurring_burn,
        "one_time_expenses_cents_30d": one_time_expenses,
        "cash_on_hand_cents": cash_on_hand,
        "runway_months": runway_months,
        "logo_churn_pct_month": None,
        "revenue_churn_pct_month": None,
        "arpa_cents": arpa,
        "warnings": warnings,
        "_comparisons": {
            "previous_mrr_cents_30d": previous_mrr,
            "previous_refunds_cents_30d": refunds_prev,
        },
    }


def _distinct_customers(transactions: list[Transaction]) -> int:
    customers = {
        txn.customer_ref
        for txn in transactions
        if txn.customer_ref and txn.type == "revenue" and txn.subtype in {"subscription_invoice", "recurring_revenue"}
    }
    return len(customers)


def _currency_for_transactions(transactions: list[Transaction]) -> str:
    for transaction in transactions:
        return transaction.currency
    return "USD"


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
