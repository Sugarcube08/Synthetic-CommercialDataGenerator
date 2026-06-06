# 01 — Customer Segmentation Model

## 1.1 Overview

Every generated customer is assigned a **6-dimensional behavioral profile** composed of independent segment axes. These segments drive all downstream data generation — sales patterns, payment behavior, return rates, and lifecycle trajectories.

The segmentation model is designed to produce the **full spectrum** of customer archetypes observed in real wholesale distribution businesses.

## 1.2 Segment Dimensions

```
┌─────────────────────────────────────────────────────────────┐
│                   CUSTOMER PROFILE                          │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │   Volume     │  │  Frequency  │  │    Payment        │   │
│  │   Segment    │  │  Segment    │  │    Behavior       │   │
│  └─────────────┘  └─────────────┘  └──────────────────┘   │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │ Outstanding  │  │ Operational │  │    Lifecycle      │   │
│  │  Balance     │  │ Discipline  │  │    Stage          │   │
│  └─────────────┘  └─────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 1.3 Dimension 1: Purchase Volume

Controls the **monetary size** of each order.

| Segment | Weight | Avg Order Value | Order Size Range | Revenue Share |
|---------|--------|-----------------|------------------|---------------|
| **Whale** | 5% | ₹50,000–₹5,00,000 | 100–5000 units | ~60% |
| **Medium** | 30% | ₹10,000–₹75,000 | 20–500 units | ~30% |
| **Small** | 65% | ₹1,000–₹15,000 | 1–50 units | ~10% |

**Distribution:** Weights above produce a Pareto-like revenue concentration where ~5% of customers (whales) generate ~60% of total revenue.

### Parameter Derivation

```python
@dataclass
class VolumeParams:
    avg_order_value_mean: float    # Log-normal μ
    avg_order_value_std: float     # Log-normal σ
    order_size_min: int
    order_size_max: int
    items_per_order_mean: float    # How many line items per order

VOLUME_CONFIGS = {
    "whale":  VolumeParams(11.5, 0.6, 100, 5000, 8.0),
    "medium": VolumeParams(10.0, 0.5, 20,  500,  4.0),
    "small":  VolumeParams(8.5,  0.4, 1,   50,   1.5),
}
```

---

## 1.4 Dimension 2: Purchase Frequency

Controls **how often** a customer places orders.

| Segment | Weight | Avg Days Between Orders | Monthly Orders | Seasonality |
|---------|--------|------------------------|----------------|-------------|
| **Frequent** | 25% | 3–10 days | 8–15 | Mild |
| **Occasional** | 35% | 15–45 days | 1–3 | None |
| **Seasonal** | 25% | Clustered in season | 0–10 (varies) | Strong |
| **Rare/One-time** | 15% | 60–365 days | 0–1 | None |

### Seasonality Model (Seasonal Buyers)

Seasonal buyers have amplified activity during specific months:

```python
SEASONAL_PATTERNS = {
    "festival_heavy": {
        # Diwali/Navratri period (Sep-Nov) + year-end
        "peak_months": [9, 10, 11, 12],
        "peak_multiplier": 3.0,
        "trough_multiplier": 0.2,
    },
    "summer_heavy": {
        "peak_months": [3, 4, 5, 6],
        "peak_multiplier": 2.5,
        "trough_multiplier": 0.4,
    },
    "year_end_heavy": {
        "peak_months": [1, 2, 3, 11, 12],
        "peak_multiplier": 2.0,
        "trough_multiplier": 0.5,
    },
}
```

---

## 1.5 Dimension 3: Payment Behavior

Controls **when and how** a customer pays invoices.

| Segment | Weight | Days After Invoice | Std Dev | Full Payment % |
|---------|--------|-------------------|---------|----------------|
| **Hyper Payer** | 10% | −5 to 0 (before due) | 2 | 98% |
| **Fast Payer** | 25% | 1–7 | 3 | 90% |
| **Moderate Payer** | 30% | 20–30 (near due date) | 5 | 75% |
| **Delayed Payer** | 25% | 35–60 | 10 | 50% |
| **Chronic Late** | 10% | 60–180 | 30 | 25% |

### Payment Splitting Model

| Segment | Probability of Split Payment | Max Splits |
|---------|------|-------------|
| Hyper Payer | 5% | 1 (always full) |
| Fast Payer | 10% | 2 |
| Moderate Payer | 30% | 3 |
| Delayed Payer | 50% | 4 |
| Chronic Late | 70% | 6 |

---

## 1.6 Dimension 4: Outstanding Balance Behavior

Controls the **debt profile** of a customer over time.

| Segment | Weight | Target Outstanding Ratio | Balance Trend |
|---------|--------|------------------------|---------------|
| **Fast Clearer** | 25% | < 5% of credit limit | Rapidly declining |
| **Outstanding Maintainer** | 30% | 20–40% of credit limit | Stable |
| **High Credit Utilizer** | 20% | 70–95% of credit limit | Near ceiling |
| **Balanced Trader** | 25% | 30–50% of credit limit | Fluctuating |

**Outstanding Ratio** = total_balance_due / credit_limit

---

## 1.7 Dimension 5: Operational Discipline

Controls the **predictability and consistency** of behavior.

| Segment | Weight | Order Variance | Payment Variance | Return Rate Multiplier |
|---------|--------|---------------|-----------------|----------------------|
| **Disciplined** | 30% | Low (CV < 0.15) | Low (CV < 0.10) | 0.5× |
| **Moderate** | 45% | Medium (CV 0.15–0.35) | Medium (CV 0.10–0.25) | 1.0× |
| **Undisciplined** | 25% | High (CV > 0.35) | High (CV > 0.25) | 2.0× |

**CV** = Coefficient of Variation (std / mean)

---

## 1.8 Dimension 6: Business Lifecycle

Controls how customer behavior **evolves over time**.

| Segment | Weight | Volume Trend | Frequency Trend | Duration |
|---------|--------|-------------|----------------|----------|
| **Growing** | 20% | +2–8% monthly | Increasing | Full period |
| **Stable** | 35% | ±1% monthly | Constant | Full period |
| **Declining** | 25% | −2–6% monthly | Decreasing | Full period |
| **Churn-Risk** | 20% | −10–20% monthly (later) | Sharp decline | Active → Inactive |

### Lifecycle Trajectory Curves

```
Volume │
       │     Growing
       │    ╱‾‾‾‾‾‾‾
       │   ╱
       │──╱── Stable ──────────
       │ ╱           ╲
       │╱             ╲ Declining
       │               ╲
       │                ╲___  Churn
       │                    ╲___
       └──────────────────────── Time
```

### Churn-Risk Specifics

- Active period: 40–80% of the date range
- Decline period: 10–30% of the date range
- Inactive period: remaining (zero transactions)
- Optional "reactivation" blip with 10% probability

---

## 1.9 Segment Combination Rules

All 6 dimensions are **independently assigned** using their respective weight distributions, creating a combinatorial space of:

```
3 × 4 × 5 × 4 × 3 × 4 = 2,880 unique archetype combinations
```

### Correlation Adjustments

While segments are largely independent, certain combinations are adjusted for realism:

| Rule | Adjustment |
|------|-----------|
| Whale + Chronic Late | Reduce probability by 50% (large customers usually negotiate better terms) |
| Small + Hyper Payer | Reduce probability by 30% (small customers rarely prepay) |
| Growing + Churn-Risk | Mutually exclusive |
| Undisciplined + Fast Clearer | Reduce probability by 40% |
| Whale + Rare | Reduce probability by 70% (whales buy frequently) |

These adjustments are applied via **rejection sampling**: generate a profile, check constraints, accept or re-roll.

---

## 1.10 Profile Distribution Validation

After generating all customer profiles, the system validates:

1. **Revenue Pareto:** Top 20% of customers by assigned volume MUST account for ≥ 75% of expected revenue
2. **Segment Coverage:** Every segment value has ≥ 1 customer (for datasets > 100 customers)
3. **Lifecycle Balance:** No single lifecycle segment exceeds 45% of customers
4. **Payment Spread:** At least 3 payment segments are represented

Validation failures trigger profile redistribution with adjusted weights.
