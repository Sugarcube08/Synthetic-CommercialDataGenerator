# 06 — Statistical Realism Engine

## 6.1 Purpose

The Statistical Realism Engine ensures that the generated dataset exhibits the same distributional properties, KPI ranges, and concentration patterns observed in real wholesale businesses. It operates at two levels:

1. **Pre-generation:** Calibrates customer profiles to produce target distributions
2. **Post-generation:** Validates output against KPI benchmarks

## 6.2 Target KPI Benchmarks

These benchmarks are derived from industry standards for Indian wholesale distribution businesses:

| KPI | Target Range | Formula |
|-----|-------------|---------|
| **Days Sales Outstanding (DSO)** | 35–75 days | (Avg Accounts Receivable / Total Credit Sales) × Days |
| **Collection Efficiency** | 70–95% | (Total Payments / Total Invoiced) × 100 |
| **Customer Lifetime Value (CLV)** | Varies by segment | Total Revenue − Returns over customer lifetime |
| **Revenue Concentration (Pareto)** | Top 20% → 75–85% revenue | Gini coefficient ≈ 0.6–0.8 |
| **Return Rate** | 3–8% | (Return Value / Total Sales) × 100 |
| **Repeat Purchase Rate** | 60–80% | Customers with 2+ orders / Total Customers |
| **Customer Churn Rate** | 10–25% annual | Customers inactive > 6 months / Total |
| **Average Payment Delay** | 25–50 days | Mean(payment_date − invoice_date) |
| **Outstanding Balance Ratio** | 15–35% | Total Outstanding / Total Invoiced |

## 6.3 Pareto Revenue Distribution

### The 80/20 Rule Implementation

The revenue concentration follows a Pareto distribution where a small fraction of customers dominates revenue. This is implemented through the volume segment assignment.

```python
def enforce_pareto_distribution(
    profiles: list[CustomerProfile],
    target_gini: float = 0.70,
    tolerance: float = 0.05,
) -> list[CustomerProfile]:
    """Adjust revenue allocations to achieve target Gini coefficient."""

    # Calculate expected revenue per customer based on profiles
    revenues = [estimate_annual_revenue(p) for p in profiles]

    # Compute current Gini
    current_gini = compute_gini(revenues)

    if abs(current_gini - target_gini) <= tolerance:
        return profiles  # Already within target

    # Adjust: redistribute whale/medium/small weights
    if current_gini < target_gini:
        # Need more concentration → boost whales, reduce small
        adjustment = "increase_concentration"
    else:
        # Too concentrated → distribute more evenly
        adjustment = "decrease_concentration"

    return redistribute_profiles(profiles, adjustment, target_gini)


def compute_gini(values: list[float]) -> float:
    """Compute the Gini coefficient for a list of values."""
    sorted_values = sorted(values)
    n = len(sorted_values)
    cumulative = numpy.cumsum(sorted_values)
    return (2 * numpy.sum((numpy.arange(1, n + 1) * sorted_values))) / (n * cumulative[-1]) - (n + 1) / n
```

### Revenue Assignment by Volume

```python
def estimate_annual_revenue(profile: CustomerProfile) -> float:
    """Estimate annual revenue from profile parameters."""

    orders_per_year = 365 / profile.order_frequency_days
    avg_items = profile.items_per_order
    avg_value = profile.avg_order_value

    base_revenue = orders_per_year * avg_items * avg_value

    # Apply lifecycle modifier
    if profile.lifecycle_segment == LifecycleSegment.GROWING:
        modifier = 1.0 + (profile.growth_rate_monthly * 6)  # Mid-year average
    elif profile.lifecycle_segment == LifecycleSegment.DECLINING:
        modifier = 1.0 + (profile.growth_rate_monthly * 6)  # Negative growth
    elif profile.lifecycle_segment == LifecycleSegment.CHURN_RISK:
        modifier = profile.churn_active_ratio * 0.7
    else:
        modifier = 1.0

    return base_revenue * modifier
```

## 6.4 Distribution Samplers

### Log-Normal Distribution (Order Values)

Used for order values because real commercial transaction amounts are right-skewed:

```python
def sample_order_value(
    mu: float,
    sigma: float,
    rng: numpy.random.Generator,
    min_value: float = 100.0,
    max_value: float = 10_000_000.0,
) -> float:
    """Sample from truncated log-normal distribution."""
    value = rng.lognormal(mu, sigma)
    return round(numpy.clip(value, min_value, max_value), 2)
```

### Beta Distribution (Proportions)

Used for discount percentages, return ratios, and payment splits:

```python
def sample_proportion(
    alpha: float,
    beta_param: float,
    rng: numpy.random.Generator,
) -> float:
    """Sample a proportion [0, 1] from Beta distribution."""
    return rng.beta(alpha, beta_param)
```

### Truncated Normal (Payment Delays)

Used for payment timing to ensure realistic bounds:

```python
def sample_truncated_normal(
    mean: float,
    std: float,
    low: float,
    high: float,
    rng: numpy.random.Generator,
) -> float:
    """Sample from truncated normal distribution."""
    while True:
        value = rng.normal(mean, std)
        if low <= value <= high:
            return value
```

### Poisson Distribution (Event Counts)

Used for number of orders per period, number of returns:

```python
def sample_event_count(
    rate: float,
    rng: numpy.random.Generator,
) -> int:
    """Sample event count from Poisson distribution."""
    return rng.poisson(rate)
```

## 6.5 Post-Generation Validation

After generation completes, the engine runs KPI validation:

```python
@dataclass
class KPIReport:
    dso: float
    collection_efficiency: float
    return_rate: float
    repeat_purchase_rate: float
    churn_rate: float
    gini_coefficient: float
    revenue_top20_pct: float
    avg_payment_delay: float
    outstanding_ratio: float
    all_passed: bool
    details: dict[str, bool]

async def validate_kpis(engine: AsyncEngine) -> KPIReport:
    """Run KPI validation queries against generated data."""

    async with engine.connect() as conn:
        dso = await compute_dso(conn)
        collection_eff = await compute_collection_efficiency(conn)
        return_rate = await compute_return_rate(conn)
        # ... etc

    checks = {
        "dso_in_range": 35 <= dso <= 75,
        "collection_eff_in_range": 0.70 <= collection_eff <= 0.95,
        "return_rate_in_range": 0.03 <= return_rate <= 0.08,
        "pareto_valid": revenue_top20_pct >= 0.75,
    }

    return KPIReport(
        dso=dso,
        collection_efficiency=collection_eff,
        return_rate=return_rate,
        all_passed=all(checks.values()),
        details=checks,
        # ...
    )
```

## 6.6 Calibration Feedback Loop

If post-generation KPIs fall outside target ranges, the system logs warnings but does NOT regenerate data (to avoid infinite loops). Instead:

1. KPI deviations are reported in the generation response
2. Users can adjust generation parameters and re-run
3. Future versions may support automatic recalibration

```
Generate → Validate → Report
              │
         ┌────┴────┐
      Pass        Fail
       │            │
    Complete    Log warnings
                + Report deviations
```
