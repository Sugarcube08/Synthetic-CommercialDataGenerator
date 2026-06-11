from datetime import date, timedelta
import numpy as np

from synth_data_creator.generation.customers.profiles import CustomerProfile
from synth_data_creator.generation.customers.segments import PaymentSegment

from synth_data_creator.generation.events import get_event_modifiers

def calculate_payment_date(
    invoice_date: date,
    profile: CustomerProfile,
    rng: np.random.Generator,
) -> date:
    """Calculate when the customer will make a payment."""
    # Get event modifiers
    mods = get_event_modifiers(invoice_date, profile.business_type)
    delay_mult = mods["delay_mult"]

    # Sample delay from profile distribution
    raw_delay = rng.normal(
        profile.payment_delay_mean,
        profile.payment_delay_std
    )

    # Add discipline noise
    noise = rng.normal(0, profile.discipline_cv * 10)
    delay_days = int((raw_delay + noise) * delay_mult)

    # Apply limits/clamping based on payment segment, scaled by delay_mult
    if profile.payment_segment == PaymentSegment.HYPER:
        delay_days = max(int(-10 * delay_mult), min(delay_days, int(5 * delay_mult)))
    elif profile.payment_segment == PaymentSegment.FAST:
        delay_days = max(int(1 * delay_mult), min(delay_days, int(15 * delay_mult)))
    elif profile.payment_segment == PaymentSegment.MODERATE:
        delay_days = max(int(15 * delay_mult), min(delay_days, int(40 * delay_mult)))
    elif profile.payment_segment == PaymentSegment.DELAYED:
        delay_days = max(int(30 * delay_mult), min(delay_days, int(90 * delay_mult)))
    else:  # CHRONIC_LATE
        delay_days = max(int(45 * delay_mult), min(delay_days, int(365 * delay_mult)))

    return invoice_date + timedelta(days=delay_days)


def split_payment(
    total: float,
    num_splits: int,
    rng: np.random.Generator,
) -> list[float]:
    """Split a payment into unequal installments."""
    if num_splits <= 1 or total <= 0.01:
        return [total]

    # Generate random proportions using Dirichlet distribution
    proportions = rng.dirichlet(np.ones(num_splits) * 2.0)

    # Sort descending (first payment is usually largest)
    proportions = sorted(proportions, reverse=True)

    amounts = [round(total * p, 2) for p in proportions]

    # Adjust last payment for rounding errors
    amounts[-1] = round(total - sum(amounts[:-1]), 2)

    # Ensure no zero payments due to rounding
    for i in range(len(amounts)):
        if amounts[i] <= 0:
            amounts[i] = 0.01
    amounts[-1] = round(total - sum(amounts[:-1]), 2)

    return amounts


def spread_payment_dates(
    first_date: date,
    num_payments: int,
    rng: np.random.Generator,
) -> list[date]:
    """Generate dates for split payments."""
    dates = [first_date]
    for _ in range(num_payments - 1):
        gap = rng.integers(7, 46)  # 1–6 weeks between partial payments
        dates.append(dates[-1] + timedelta(days=int(gap)))
    return dates


PAYMENT_MODE_WEIGHTS = {
    "bank_transfer": 0.30,
    "neft": 0.25,
    "rtgs": 0.15,   # For large amounts
    "cheque": 0.12,
    "upi": 0.10,
    "cash": 0.05,
    "credit_note": 0.03,
}

def select_payment_mode(
    amount: float,
    rng: np.random.Generator,
) -> str:
    """Select payment mode, biased by amount."""
    if amount > 200_000:
        # Large payments prefer RTGS/NEFT
        weights = {**PAYMENT_MODE_WEIGHTS, "rtgs": 0.40, "cash": 0.01, "upi": 0.02}
    elif amount < 5_000:
        weights = {**PAYMENT_MODE_WEIGHTS, "upi": 0.30, "cash": 0.15}
    else:
        weights = PAYMENT_MODE_WEIGHTS

    modes = list(weights.keys())
    probs = np.array(list(weights.values()))
    probs /= probs.sum()
    return str(rng.choice(modes, p=probs))


def compute_invoice_status(
    invoice_amount: float,
    total_paid: float,
    due_date: date,
    reference_date: date,  # "today" in the simulation
) -> tuple[str, float]:
    """Compute payment_status and balance_due."""
    balance = round(invoice_amount - total_paid, 2)

    if balance <= 0.01:
        return "paid", 0.0
    elif total_paid > 0:
        if reference_date > due_date:
            return "overdue", balance
        return "partial", balance
    else:
        if reference_date > due_date:
            return "overdue", balance
        return "unpaid", balance


