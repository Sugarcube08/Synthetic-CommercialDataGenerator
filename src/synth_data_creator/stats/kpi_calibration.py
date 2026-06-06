from typing import Any

def calibrate_kpis(
    dso: float,
    collection_efficiency: float,
    return_rate: float,
    gini_coefficient: float,
    revenue_top20_pct: float,
    repeat_purchase_rate: float,
    churn_rate: float,
    avg_payment_delay_days: float,
    outstanding_ratio: float,
) -> dict[str, Any]:
    """Validate calculated KPIs against target industry benchmarks.

    Returns a dictionary of boolean checks and an overall pass flag.
    """
    checks = {
        "dso_in_range": 35.0 <= dso <= 75.0,
        "collection_efficiency_in_range": 0.70 <= collection_efficiency <= 0.95,
        "return_rate_in_range": 0.03 <= return_rate <= 0.08,
        "pareto_valid": revenue_top20_pct >= 0.75,
        "repeat_purchase_rate_valid": repeat_purchase_rate >= 0.60,
        "gini_valid": 0.60 <= gini_coefficient <= 0.85,
    }

    all_passed = all(checks.values())

    return {
        "all_passed": all_passed,
        "checks": checks,
    }
