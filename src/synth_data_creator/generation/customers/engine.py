from datetime import date, timedelta
from faker import Faker
import numpy as np

from synth_data_creator.generation.customers.profiles import CustomerProfile
from synth_data_creator.generation.customers.segments import (
    DisciplineSegment,
    FrequencySegment,
    LifecycleSegment,
    OutstandingSegment,
    PaymentSegment,
    VolumeSegment,
    VOLUME_CONFIGS,
    SEASONAL_PATTERNS,
)

def assign_registration_date(
    start_date: date,
    end_date: date,
    lifecycle: LifecycleSegment,
    rng: np.random.Generator,
) -> date:
    """Assign a customer registration date based on their lifecycle segment."""
    total_days = (end_date - start_date).days
    if total_days <= 0:
        return start_date

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
    else:
        day_offset = int(rng.uniform(0, total_days * 0.8))

    return start_date + timedelta(days=max(0, min(day_offset, total_days)))


def generate_single_profile(
    customer_idx: int,
    start_date: date,
    end_date: date,
    rng: np.random.Generator,
    fake: Faker,
) -> CustomerProfile:
    """Generate a single customer profile, enforcing correlation constraints via rejection sampling."""
    
    # Rejection sampling loop for segment assignment
    max_attempts = 100
    for _ in range(max_attempts):
        # 1. Base weights for segments
        volume = VolumeSegment(rng.choice(
            [VolumeSegment.WHALE.value, VolumeSegment.MEDIUM.value, VolumeSegment.SMALL.value],
            p=[0.05, 0.30, 0.65],
        ))
        frequency = FrequencySegment(rng.choice(
            [FrequencySegment.FREQUENT.value, FrequencySegment.OCCASIONAL.value, FrequencySegment.SEASONAL.value, FrequencySegment.RARE.value],
            p=[0.25, 0.35, 0.25, 0.15],
        ))
        payment = PaymentSegment(rng.choice(
            [PaymentSegment.HYPER.value, PaymentSegment.FAST.value, PaymentSegment.MODERATE.value, PaymentSegment.DELAYED.value, PaymentSegment.CHRONIC_LATE.value],
            p=[0.10, 0.25, 0.30, 0.25, 0.10],
        ))
        outstanding = OutstandingSegment(rng.choice(
            [OutstandingSegment.FAST_CLEARER.value, OutstandingSegment.MAINTAINER.value, OutstandingSegment.HIGH_UTILIZER.value, OutstandingSegment.BALANCED.value],
            p=[0.25, 0.30, 0.20, 0.25],
        ))
        discipline = DisciplineSegment(rng.choice(
            [DisciplineSegment.DISCIPLINED.value, DisciplineSegment.MODERATE.value, DisciplineSegment.UNDISCIPLINED.value],
            p=[0.30, 0.45, 0.25],
        ))
        lifecycle = LifecycleSegment(rng.choice(
            [LifecycleSegment.GROWING.value, LifecycleSegment.STABLE.value, LifecycleSegment.DECLINING.value, LifecycleSegment.CHURN_RISK.value],
            p=[0.20, 0.35, 0.25, 0.20],
        ))



        # 2. Check correlation constraints
        # Whale + Chronic Late: Reduce probability by 50%
        if volume == VolumeSegment.WHALE and payment == PaymentSegment.CHRONIC_LATE:
            if rng.random() < 0.5:
                continue
                
        # Small + Hyper Payer: Reduce probability by 30%
        if volume == VolumeSegment.SMALL and payment == PaymentSegment.HYPER:
            if rng.random() < 0.3:
                continue
                
        # Growing + Churn-Risk: Mutually exclusive
        if lifecycle == LifecycleSegment.GROWING and lifecycle == LifecycleSegment.CHURN_RISK:
            continue  # Naturally impossible since a variable can't be both, but keep logic
            
        # Undisciplined + Fast Clearer: Reduce probability by 40%
        if discipline == DisciplineSegment.UNDISCIPLINED and outstanding == OutstandingSegment.FAST_CLEARER:
            if rng.random() < 0.4:
                continue
                
        # Whale + Rare: Reduce probability by 70%
        if volume == VolumeSegment.WHALE and frequency == FrequencySegment.RARE:
            if rng.random() < 0.7:
                continue
                
        break

    # 3. Derive numeric parameters
    # Volume -> avg_order_value, credit_limit, payment_terms_days
    v_cfg = VOLUME_CONFIGS[volume]
    # Sample avg_order_value from log-normal (μ, σ)
    raw_aov = rng.lognormal(v_cfg.avg_order_value_mean, v_cfg.avg_order_value_std)
    avg_order_value = round(float(np.clip(raw_aov, 100.0, 10_000_000.0)), 2)
    order_value_std = round(avg_order_value * rng.uniform(0.15, 0.35), 2)
    
    if volume == VolumeSegment.WHALE:
        credit_limit = round(float(rng.uniform(1_000_000.0, 10_000_000.0)), 2)
        payment_terms_days = int(rng.choice([45, 60, 90]))
    elif volume == VolumeSegment.MEDIUM:
        credit_limit = round(float(rng.uniform(200_000.0, 1_500_000.0)), 2)
        payment_terms_days = int(rng.choice([30, 45, 60]))
    else:  # SMALL
        credit_limit = round(float(rng.uniform(25_000.0, 300_000.0)), 2)
        payment_terms_days = int(rng.choice([15, 30]))

    # Discipline CV noise
    if discipline == DisciplineSegment.DISCIPLINED:
        discipline_cv = float(rng.uniform(0.05, 0.15))
        base_return_prob = 0.02
    elif discipline == DisciplineSegment.MODERATE:
        discipline_cv = float(rng.uniform(0.15, 0.35))
        base_return_prob = 0.05
    else:  # UNDISCIPLINED
        discipline_cv = float(rng.uniform(0.35, 0.55))
        base_return_prob = 0.10

    # Frequency -> order_frequency_days
    if frequency == FrequencySegment.FREQUENT:
        order_frequency_days = float(rng.uniform(3.0, 10.0))
    elif frequency == FrequencySegment.OCCASIONAL:
        order_frequency_days = float(rng.uniform(15.0, 45.0))
    elif frequency == FrequencySegment.SEASONAL:
        order_frequency_days = float(rng.uniform(7.0, 21.0))
    else:  # RARE
        order_frequency_days = float(rng.uniform(60.0, 365.0))
        
    order_frequency_std = order_frequency_days * discipline_cv
    items_per_order = max(1.0, round(float(rng.normal(v_cfg.items_per_order_mean, v_cfg.items_per_order_mean * 0.2)), 1))

    # Seasonality parameters
    seasonal_pattern = None
    seasonal_peak_months = ()
    seasonal_peak_multiplier = 1.0
    seasonal_trough_multiplier = 1.0
    if frequency == FrequencySegment.SEASONAL:
        seasonal_pattern = rng.choice(list(SEASONAL_PATTERNS.keys()))
        sp_cfg = SEASONAL_PATTERNS[seasonal_pattern]
        seasonal_peak_months = sp_cfg["peak_months"]
        seasonal_peak_multiplier = sp_cfg["peak_multiplier"]
        seasonal_trough_multiplier = sp_cfg["trough_multiplier"]

    # Payment timing delay
    if payment == PaymentSegment.HYPER:
        payment_delay_mean = float(rng.uniform(-5.0, 0.0))
        payment_delay_std = 2.0
        full_payment_probability = 0.98
        max_payment_splits = 1
    elif payment == PaymentSegment.FAST:
        payment_delay_mean = float(rng.uniform(1.0, 7.0))
        payment_delay_std = 3.0
        full_payment_probability = 0.90
        max_payment_splits = 2
    elif payment == PaymentSegment.MODERATE:
        payment_delay_mean = float(rng.uniform(20.0, 30.0))
        payment_delay_std = 5.0
        full_payment_probability = 0.75
        max_payment_splits = 3
    elif payment == PaymentSegment.DELAYED:
        payment_delay_mean = float(rng.uniform(35.0, 60.0))
        payment_delay_std = 10.0
        full_payment_probability = 0.50
        max_payment_splits = 4
    else:  # CHRONIC_LATE
        payment_delay_mean = float(rng.uniform(60.0, 180.0))
        payment_delay_std = 30.0
        full_payment_probability = 0.25
        max_payment_splits = 6

    # Lifecycle parameters
    if lifecycle == LifecycleSegment.GROWING:
        growth_rate_monthly = float(rng.uniform(0.02, 0.08))
        churn_active_ratio = 1.0
    elif lifecycle == LifecycleSegment.STABLE:
        growth_rate_monthly = float(rng.uniform(-0.01, 0.01))
        churn_active_ratio = 1.0
    elif lifecycle == LifecycleSegment.DECLINING:
        growth_rate_monthly = float(rng.uniform(-0.06, -0.02))
        churn_active_ratio = 1.0
    else:  # CHURN_RISK
        growth_rate_monthly = float(rng.uniform(-0.20, -0.10))
        churn_active_ratio = float(rng.uniform(0.40, 0.80))

    # Faker metadata
    business_name = fake.company()
    contact_name = fake.name()
    email = fake.company_email()
    phone = fake.phone_number()
    address_line1 = fake.street_address()
    city = fake.city()
    state = fake.state()
    postal_code = fake.postcode()
    business_type = rng.choice(
        ["retailer", "distributor", "manufacturer", "wholesaler"],
        p=[0.50, 0.25, 0.15, 0.10]
    )

    registration_date = assign_registration_date(start_date, end_date, lifecycle, rng)
    customer_code = f"CUST-{customer_idx:05d}"
    per_cust_seed = int(rng.integers(0, 1_000_000))

    return CustomerProfile(
        customer_code=customer_code,
        business_name=business_name,
        contact_name=contact_name,
        email=email,
        phone=phone,
        address_line1=address_line1,
        address_line2="",
        city=city,
        state=state,
        postal_code=postal_code,
        country="IND",
        business_type=business_type,
        registration_date=registration_date,
        volume_segment=volume,
        frequency_segment=frequency,
        payment_segment=payment,
        outstanding_segment=outstanding,
        discipline_segment=discipline,
        lifecycle_segment=lifecycle,
        credit_limit=credit_limit,
        payment_terms_days=payment_terms_days,
        avg_order_value=avg_order_value,
        order_value_std=order_value_std,
        order_frequency_days=order_frequency_days,
        order_frequency_std=order_frequency_std,
        items_per_order=items_per_order,
        payment_delay_mean=payment_delay_mean,
        payment_delay_std=payment_delay_std,
        full_payment_probability=full_payment_probability,
        max_payment_splits=max_payment_splits,
        return_probability=base_return_prob,
        growth_rate_monthly=growth_rate_monthly,
        seasonal_pattern=seasonal_pattern,
        seasonal_peak_months=seasonal_peak_months,
        seasonal_peak_multiplier=seasonal_peak_multiplier,
        seasonal_trough_multiplier=seasonal_trough_multiplier,
        discipline_cv=discipline_cv,
        churn_active_ratio=churn_active_ratio,
        rng_seed=per_cust_seed,
    )


def estimate_annual_revenue(profile: CustomerProfile) -> float:
    """Estimate annual revenue from profile parameters."""
    orders_per_year = 365.0 / profile.order_frequency_days
    avg_items = profile.items_per_order
    avg_value = profile.avg_order_value

    base_revenue = orders_per_year * avg_items * avg_value

    if profile.lifecycle_segment == LifecycleSegment.GROWING:
        modifier = 1.0 + (profile.growth_rate_monthly * 6)  # Mid-year average
    elif profile.lifecycle_segment == LifecycleSegment.DECLINING:
        modifier = 1.0 + (profile.growth_rate_monthly * 6)  # Negative growth
    elif profile.lifecycle_segment == LifecycleSegment.CHURN_RISK:
        modifier = profile.churn_active_ratio * 0.7
    else:
        modifier = 1.0

    return base_revenue * modifier


def generate_profiles(
    num_customers: int,
    start_date: date,
    end_date: date,
    seed: int | None = None,
) -> list[CustomerProfile]:
    """Generate a validated list of customer profiles."""
    rng = np.random.default_rng(seed)
    fake = Faker("en_IN")
    if seed is not None:
        fake.seed_instance(seed)

    profiles = []
    for idx in range(1, num_customers + 1):
        # Use customer specific seed for Faker to keep it reproducible
        fake.seed_instance(seed + idx if seed is not None else idx)
        profile = generate_single_profile(idx, start_date, end_date, rng, fake)
        profiles.append(profile)

    return profiles
