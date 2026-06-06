from datetime import date
import pytest

from synth_data_creator.generation.customers.engine import generate_profiles
from synth_data_creator.generation.customers.segments import (
    DisciplineSegment,
    FrequencySegment,
    LifecycleSegment,
    OutstandingSegment,
    PaymentSegment,
    VolumeSegment,
)

def test_profile_segment_assignment() -> None:
    """Verify generated profiles have valid segments."""
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    profiles = generate_profiles(10, start, end, seed=42)
    
    assert len(profiles) == 10
    for p in profiles:
        assert isinstance(p.volume_segment, VolumeSegment)
        assert isinstance(p.frequency_segment, FrequencySegment)
        assert isinstance(p.payment_segment, PaymentSegment)
        assert isinstance(p.outstanding_segment, OutstandingSegment)
        assert isinstance(p.discipline_segment, DisciplineSegment)
        assert isinstance(p.lifecycle_segment, LifecycleSegment)


def test_profile_immutability() -> None:
    """Frozen dataclass attributes cannot be mutated."""
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    profiles = generate_profiles(1, start, end, seed=42)
    p = profiles[0]
    
    with pytest.raises(AttributeError):
        # type ignore is used because static typecheck knows it's frozen
        p.business_name = "New Business Name"  # type: ignore


def test_registration_date_bounds() -> None:
    """All registration dates are within range."""
    start = date(2023, 1, 1)
    end = date(2024, 12, 31)
    profiles = generate_profiles(20, start, end, seed=99)
    
    for p in profiles:
        assert start <= p.registration_date <= end


def test_deterministic_seed() -> None:
    """Same seed generates identical profiles."""
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    
    profiles_a = generate_profiles(15, start, end, seed=123)
    profiles_b = generate_profiles(15, start, end, seed=123)
    
    for pa, pb in zip(profiles_a, profiles_b):
        assert pa.customer_code == pb.customer_code
        assert pa.business_name == pb.business_name
        assert pa.volume_segment == pb.volume_segment
        assert pa.avg_order_value == pb.avg_order_value
        assert pa.credit_limit == pb.credit_limit
        assert pa.registration_date == pb.registration_date


def test_customer_code_uniqueness() -> None:
    """Verify customer codes are sequential and unique."""
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    profiles = generate_profiles(30, start, end, seed=456)
    
    codes = [p.customer_code for p in profiles]
    assert len(codes) == len(set(codes))
    assert codes[0] == "CUST-00001"
    assert codes[-1] == "CUST-00030"
