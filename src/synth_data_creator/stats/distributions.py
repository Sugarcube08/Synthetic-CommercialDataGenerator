import numpy as np

def sample_order_value(
    mu: float,
    sigma: float,
    rng: np.random.Generator,
    min_value: float = 100.0,
    max_value: float = 10_000_000.0,
) -> float:
    """Sample from a truncated log-normal distribution."""
    # Generate lognormal
    value = rng.lognormal(mu, sigma)
    # Clip to bounds
    clipped = np.clip(value, min_value, max_value)
    return round(float(clipped), 2)


def sample_proportion(
    alpha: float,
    beta_param: float,
    rng: np.random.Generator,
) -> float:
    """Sample a proportion [0, 1] from a Beta distribution."""
    return float(rng.beta(alpha, beta_param))


def sample_truncated_normal(
    mean: float,
    std: float,
    low: float,
    high: float,
    rng: np.random.Generator,
) -> float:
    """Sample from a truncated normal distribution."""
    if std <= 0:
        return float(np.clip(mean, low, high))
    
    # Simple rejection sampling for truncation, which is efficient enough for our use case
    for _ in range(100):
        value = rng.normal(mean, std)
        if low <= value <= high:
            return float(value)
            
    # Fallback to clip if we fail to sample within 100 tries (very unlikely unless bounds are extremely tight)
    return float(np.clip(rng.normal(mean, std), low, high))


def sample_event_count(
    rate: float,
    rng: np.random.Generator,
) -> int:
    """Sample event count from a Poisson distribution."""
    return int(rng.poisson(rate))
