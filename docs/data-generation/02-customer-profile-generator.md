# 02 — Customer Profile Generator

## 2.1 Overview

The Customer Profile Generator creates a complete `CustomerProfile` object for each customer. This profile is a **frozen, immutable dataclass** that serves as the single source of truth for all downstream data generation engines.

## 2.2 Generation Pipeline

```
Input: num_customers, seed, date_range
                │
                ▼
┌──────────────────────────┐
│ 1. Initialize RNG        │ ← numpy.random.Generator(seed)
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 2. Assign Revenue Tiers  │ ← Pareto-weighted volume assignment
│    (Whale/Med/Small)     │     ensures 80/20 concentration
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 3. Assign Segments       │ ← Weighted random per dimension
│    (6 dimensions)        │     with correlation adjustments
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 4. Derive Parameters     │ ← Convert segments to numeric
│                          │     parameters using distributions
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 5. Generate Metadata     │ ← Faker: names, addresses, codes
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 6. Validate Profiles     │ ← Pareto check, segment coverage
└──────────┬───────────────┘
           │
           ▼
       List[CustomerProfile]
```

## 2.3 CustomerProfile Dataclass

```python
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from uuid import UUID, uuid4

class VolumeSegment(str, Enum):
    WHALE = "whale"
    MEDIUM = "medium"
    SMALL = "small"

class FrequencySegment(str, Enum):
    FREQUENT = "frequent"
    OCCASIONAL = "occasional"
    SEASONAL = "seasonal"
    RARE = "rare"

class PaymentSegment(str, Enum):
    HYPER = "hyper_payer"
    FAST = "fast_payer"
    MODERATE = "moderate_payer"
    DELAYED = "delayed_payer"
    CHRONIC_LATE = "chronic_late"

class OutstandingSegment(str, Enum):
    FAST_CLEARER = "fast_clearer"
    MAINTAINER = "outstanding_maintainer"
    HIGH_UTILIZER = "high_credit_utilizer"
    BALANCED = "balanced_trader"

class DisciplineSegment(str, Enum):
    DISCIPLINED = "disciplined"
    MODERATE = "moderate"
    UNDISCIPLINED = "undisciplined"

class LifecycleSegment(str, Enum):
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    CHURN_RISK = "churn_risk"


@dataclass(frozen=True)
class CustomerProfile:
    """Immutable behavioral profile driving all data generation."""

    # Identity
    id: UUID = field(default_factory=uuid4)
    customer_code: str = ""
    business_name: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "IND"
    business_type: str = "retailer"
    registration_date: date = field(default_factory=date.today)

    # Segment assignments
    volume_segment: VolumeSegment = VolumeSegment.SMALL
    frequency_segment: FrequencySegment = FrequencySegment.OCCASIONAL
    payment_segment: PaymentSegment = PaymentSegment.MODERATE
    outstanding_segment: OutstandingSegment = OutstandingSegment.BALANCED
    discipline_segment: DisciplineSegment = DisciplineSegment.MODERATE
    lifecycle_segment: LifecycleSegment = LifecycleSegment.STABLE

    # Derived numeric parameters
    credit_limit: float = 50_000.0
    payment_terms_days: int = 30
    avg_order_value: float = 10_000.0
    order_value_std: float = 3_000.0
    order_frequency_days: float = 30.0
    order_frequency_std: float = 10.0
    items_per_order: float = 3.0
    payment_delay_mean: float = 25.0
    payment_delay_std: float = 5.0
    full_payment_probability: float = 0.75
    max_payment_splits: int = 3
    return_probability: float = 0.05
    growth_rate_monthly: float = 0.0
    seasonal_pattern: str | None = None
    seasonal_peak_months: tuple[int, ...] = ()
    seasonal_peak_multiplier: float = 1.0
    seasonal_trough_multiplier: float = 1.0
    discipline_cv: float = 0.2
    churn_active_ratio: float = 1.0

    # Per-customer RNG seed
    rng_seed: int = 0
```

## 2.4 Parameter Derivation Rules

### Volume → Financial Parameters

| Volume Segment | Credit Limit Range | Avg Order Value (log-normal) | Payment Terms |
|---------------|-------------------|------------------------------|---------------|
| Whale | ₹10L–₹1Cr | μ=11.5, σ=0.6 | 45–90 days |
| Medium | ₹2L–₹15L | μ=10.0, σ=0.5 | 30–60 days |
| Small | ₹25K–₹3L | μ=8.5, σ=0.4 | 15–30 days |

### Frequency → Ordering Parameters

| Frequency | Days Between Orders | Std Dev |
|-----------|-------------------|---------|
| Frequent | μ=7, σ=2 | Low |
| Occasional | μ=30, σ=10 | Medium |
| Seasonal | μ=varies by month | High |
| Rare | μ=120, σ=40 | Very high |

### Payment → Delay Parameters

| Payment Segment | Delay Mean (days) | Delay Std | Full Payment % | Max Splits |
|----------------|-------------------|-----------|----------------|------------|
| Hyper | −3 (prepay) | 2 | 98% | 1 |
| Fast | 5 | 3 | 90% | 2 |
| Moderate | 25 | 5 | 75% | 3 |
| Delayed | 45 | 10 | 50% | 4 |
| Chronic Late | 90 | 30 | 25% | 6 |

### Lifecycle → Growth Parameters

| Lifecycle | Monthly Growth Rate | Duration |
|-----------|-------------------|----------|
| Growing | +3% to +8% | Full range |
| Stable | ±1% | Full range |
| Declining | −3% to −6% | Full range |
| Churn-Risk | −10% to −20% (late) | 40–80% active |

## 2.5 Metadata Generation (Faker)

```python
from faker import Faker

fake = Faker("en_IN")  # Indian locale

def generate_customer_metadata(rng: numpy.random.Generator) -> dict:
    return {
        "business_name": fake.company(),
        "contact_name": fake.name(),
        "email": fake.company_email(),
        "phone": fake.phone_number(),
        "address_line1": fake.street_address(),
        "city": fake.city(),
        "state": fake.state(),
        "postal_code": fake.postcode(),
        "business_type": rng.choice(
            ["retailer", "distributor", "manufacturer", "wholesaler"],
            p=[0.50, 0.25, 0.15, 0.10]
        ),
    }
```

## 2.6 Registration Date Assignment

Customer registration dates are distributed across the date range to simulate a growing customer base:

```python
def assign_registration_date(
    start_date: date,
    end_date: date,
    lifecycle: LifecycleSegment,
    rng: numpy.random.Generator,
) -> date:
    total_days = (end_date - start_date).days

    if lifecycle == LifecycleSegment.GROWING:
        # Newer customers tend to be growing
        day_offset = int(rng.beta(2, 5) * total_days)
    elif lifecycle == LifecycleSegment.STABLE:
        # Uniformly distributed
        day_offset = int(rng.uniform(0, total_days * 0.8))
    elif lifecycle == LifecycleSegment.DECLINING:
        # Older customers tend to be declining
        day_offset = int(rng.beta(5, 2) * total_days * 0.6)
    elif lifecycle == LifecycleSegment.CHURN_RISK:
        # Early registrations that later churn
        day_offset = int(rng.beta(5, 2) * total_days * 0.5)

    return start_date + timedelta(days=day_offset)
```

## 2.7 Profile Validation

After all profiles are generated, the system runs validation:

```python
def validate_profiles(profiles: list[CustomerProfile]) -> ValidationResult:
    checks = {
        "pareto_revenue": check_pareto_concentration(profiles),
        "segment_coverage": check_all_segments_represented(profiles),
        "lifecycle_balance": check_no_segment_dominance(profiles),
        "payment_spread": check_payment_diversity(profiles),
    }
    return ValidationResult(passed=all(checks.values()), details=checks)
```

If validation fails, the generator adjusts weights and re-rolls underrepresented segments.
