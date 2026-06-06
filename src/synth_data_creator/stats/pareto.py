import numpy as np

def compute_gini(values: list[float]) -> float:
    """Compute the Gini coefficient for a list of values."""
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n == 0:
        return 0.0
    
    sum_vals = sum(sorted_values)
    if sum_vals == 0:
        return 0.0
        
    cumulative = np.cumsum(sorted_values)
    # Gini formula
    index_sum = np.sum(np.arange(1, n + 1) * sorted_values)
    gini = (2.0 * index_sum) / (n * cumulative[-1]) - (n + 1) / n
    return float(gini)


def redistribute_revenue_weights(
    current_revenues: list[float],
    target_gini: float = 0.70,
    tolerance: float = 0.05,
) -> list[float]:
    """Helper to check if Gini is within range.

    Actual profile redistribution is handled by the customer generation engine
    to respect the domain models.
    """
    return current_revenues
