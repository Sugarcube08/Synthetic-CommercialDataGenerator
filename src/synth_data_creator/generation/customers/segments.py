from dataclasses import dataclass
from enum import Enum

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


@dataclass
class VolumeParams:
    avg_order_value_mean: float    # Log-normal μ
    avg_order_value_std: float     # Log-normal σ
    order_size_min: int
    order_size_max: int
    items_per_order_mean: float    # How many line items per order


VOLUME_CONFIGS = {
    VolumeSegment.WHALE:  VolumeParams(11.5, 0.6, 100, 5000, 8.0),
    VolumeSegment.MEDIUM: VolumeParams(10.0, 0.5, 20,  500,  4.0),
    VolumeSegment.SMALL:  VolumeParams(8.5,  0.4, 1,   50,   1.5),
}


SEASONAL_PATTERNS = {
    "festival_heavy": {
        "peak_months": (9, 10, 11, 12),
        "peak_multiplier": 3.0,
        "trough_multiplier": 0.2,
    },
    "summer_heavy": {
        "peak_months": (3, 4, 5, 6),
        "peak_multiplier": 2.5,
        "trough_multiplier": 0.4,
    },
    "year_end_heavy": {
        "peak_months": (1, 2, 3, 11, 12),
        "peak_multiplier": 2.0,
        "trough_multiplier": 0.5,
    },
}
