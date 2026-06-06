from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

from synth_data_creator.generation.customers.segments import (
    DisciplineSegment,
    FrequencySegment,
    LifecycleSegment,
    OutstandingSegment,
    PaymentSegment,
    VolumeSegment,
)

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
    address_line1: str = ""
    address_line2: str = ""
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
