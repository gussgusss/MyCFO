from __future__ import annotations

from datetime import date


def build_forecast(
    *,
    current_mrr_cents: int,
    monthly_expenses_cents: int,
    as_of: date,
    horizon_months: int,
    assumptions: dict,
    variants: dict | None = None,
) -> dict:
    variants = variants or {"base": {}}
    months = []
    base_month = as_of.month
    base_year = as_of.year
    for offset in range(1, horizon_months + 1):
        month_number = base_month + offset
        year = base_year + ((month_number - 1) // 12)
        month = ((month_number - 1) % 12) + 1
        months.append(f"{year:04d}-{month:02d}")

    series = {"months": months}
    for name, overrides in variants.items():
        variant_assumptions = {**assumptions, **overrides}
        series[name] = _forecast_variant(
            current_mrr_cents=current_mrr_cents,
            monthly_expenses_cents=monthly_expenses_cents,
            months=months,
            assumptions=variant_assumptions,
        )
    return series


def _forecast_variant(
    *,
    current_mrr_cents: int,
    monthly_expenses_cents: int,
    months: list[str],
    assumptions: dict,
) -> dict:
    growth_rate = assumptions.get("mrr_growth_pct", 0) / 100
    churn_rate = assumptions.get("monthly_logo_churn_pct", 0) / 100
    gross_margin = assumptions.get("gross_margin_pct", 100) / 100
    price_uplift = assumptions.get("price_uplift_pct", 0)
    starting_cash = assumptions.get("starting_cash_cents")
    extra_hires = assumptions.get("extra_hires", [])

    mrr = current_mrr_cents * (1 + price_uplift)
    cash = starting_cash
    mrr_series = []
    burn_series = []
    cash_series = []
    runway_series = []

    for month in months:
        monthly_extra_cost = sum(item["monthly_cost_cents"] for item in extra_hires if item["start_month"] <= month)
        mrr = int(round(mrr * (1 + growth_rate - churn_rate)))
        revenue = int(round(mrr * gross_margin))
        burn = (monthly_expenses_cents + monthly_extra_cost) - revenue
        cash = None if cash is None else int(round(cash - burn))
        runway = round(cash / burn, 2) if cash is not None and burn > 0 else None

        mrr_series.append(mrr)
        burn_series.append(burn)
        cash_series.append(cash)
        runway_series.append(runway)

    return {
        "mrr_cents": mrr_series,
        "burn_cents": burn_series,
        "cash_cents": cash_series,
        "runway_months": runway_series,
    }
