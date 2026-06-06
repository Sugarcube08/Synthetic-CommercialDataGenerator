import numpy as np

from synth_data_creator.stats.distributions import (
    sample_order_value,
    sample_proportion,
    sample_truncated_normal,
)
from synth_data_creator.stats.pareto import compute_gini

def test_lognormal_sampling(seeded_rng: np.random.Generator) -> None:
    """Verify lognormal sampling returns values in range."""
    for _ in range(100):
        val = sample_order_value(mu=10.0, sigma=0.5, rng=seeded_rng, min_value=100.0, max_value=100_000.0)
        assert 100.0 <= val <= 100_000.0
        assert isinstance(val, float)


def test_proportion_sampling(seeded_rng: np.random.Generator) -> None:
    """Verify proportion sampling is bounded in [0, 1]."""
    for _ in range(100):
        val = sample_proportion(2.0, 5.0, seeded_rng)
        assert 0.0 <= val <= 1.0


def test_truncated_normal_bounds(seeded_rng: np.random.Generator) -> None:
    """Verify samples are strictly within limits."""
    for _ in range(100):
        val = sample_truncated_normal(mean=30.0, std=10.0, low=15.0, high=45.0, rng=seeded_rng)
        assert 15.0 <= val <= 45.0


def test_gini_coefficient() -> None:
    """Test Gini coefficient calculation with edge cases and known values."""
    # Equal distribution has Gini of 0
    assert compute_gini([10.0, 10.0, 10.0, 10.0]) == 0.0
    
    # Highly concentrated distribution
    gini = compute_gini([1.0, 1.0, 1.0, 97.0])
    assert 0.70 <= gini <= 0.99
    
    # Empty list
    assert compute_gini([]) == 0.0
