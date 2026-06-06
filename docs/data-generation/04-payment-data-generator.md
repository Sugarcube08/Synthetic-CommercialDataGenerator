# 04 — Payment Data Generator

## 4.1 Overview

The Payment Engine generates `raw_payments` records by iterating over all `raw_sales` invoices and simulating payment behavior according to each customer's `PaymentSegment` and `OutstandingSegment`. Payments always reference real invoices, maintaining referential integrity.

## 4.2 Generation Pipeline

```
Input: All raw_sales records (grouped by customer), CustomerProfiles
                │
                ▼
┌──────────────────────────────────────┐
│ 1. Group invoices by customer_id     │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 2. For each customer:               │
│    Sort invoices chronologically     │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 3. For each invoice:                │
│    a. Determine if paid/partial/not │ ← PaymentSegment probability
│    b. Calculate payment delay       │ ← Normal(delay_mean, delay_std)
│    c. Split into N payments         │ ← Full payment prob → split logic
│    d. Assign payment dates          │ ← Spread across delay window
│    e. Choose payment mode           │ ← Weighted random
│    f. Generate payment records      │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 4. Update invoice status fields     │ ← amount_paid, balance_due, status
└──────────┬───────────────────────────┘
           │
           ▼
       List[PaymentRecord], Updated invoices
```

## 4.3 Payment Decision Tree

For each invoice, the engine makes a series of decisions:

```
Invoice Created
       │
       ▼
  Will customer pay?
       │
   ┌───┴───┐
   Yes     No  ← (Chronic Late: 15% chance of complete non-payment)
   │        │
   │        └──▶ Invoice stays "unpaid"
   │
   ▼
  Full or Partial?
       │
   ┌───┴────┐
  Full    Partial ← (1 - full_payment_probability)
   │        │
   │        ▼
   │    How many splits?
   │        │
   │    ┌───┴───┐
   │    2  3  4+
   │    │  │   │
   ▼    ▼  ▼   ▼
  Single payment   Multiple payments
  on delay_date    spread over time
```

## 4.4 Payment Timing Model

### Base Delay Calculation

```python
def calculate_payment_date(
    invoice: SalesRecord,
    profile: CustomerProfile,
    rng: numpy.random.Generator,
) -> date:
    """Calculate when the customer will make a payment."""

    # Sample delay from profile distribution
    raw_delay = rng.normal(
        profile.payment_delay_mean,
        profile.payment_delay_std
    )

    # Add discipline noise
    noise = rng.normal(0, profile.discipline_cv * 10)
    delay_days = max(0, int(raw_delay + noise))

    # Hyper payers can have negative delay (pay before due date)
    if profile.payment_segment == PaymentSegment.HYPER:
        delay_days = max(-10, delay_days)  # Up to 10 days early

    return invoice.invoice_date + timedelta(days=delay_days)
```

### Payment Delay Distribution by Segment

| Segment | Delay Formula | Distribution |
|---------|--------------|--------------|
| Hyper | `N(−3, 2)` clamped to [-10, 5] | Prepayment |
| Fast | `N(5, 3)` clamped to [1, 15] | Quick settlement |
| Moderate | `N(25, 5)` clamped to [15, 40] | Near due date |
| Delayed | `N(45, 10)` clamped to [30, 90] | Past due |
| Chronic Late | `N(90, 30)` clamped to [45, 365] | Long outstanding |

## 4.5 Partial Payment Logic

When a payment is split, amounts are distributed unevenly to simulate realistic partial clearing:

```python
def split_payment(
    total: float,
    num_splits: int,
    rng: numpy.random.Generator,
) -> list[float]:
    """Split a payment into unequal installments."""

    # Generate random proportions using Dirichlet distribution
    proportions = rng.dirichlet(numpy.ones(num_splits) * 2)

    # Sort descending (first payment is usually largest)
    proportions = sorted(proportions, reverse=True)

    amounts = [round(total * p, 2) for p in proportions]

    # Adjust last payment for rounding
    amounts[-1] = round(total - sum(amounts[:-1]), 2)

    return amounts


def spread_payment_dates(
    first_date: date,
    num_payments: int,
    profile: CustomerProfile,
    rng: numpy.random.Generator,
) -> list[date]:
    """Generate dates for split payments."""
    dates = [first_date]
    for _ in range(num_payments - 1):
        gap = rng.integers(7, 45)  # 1–6 weeks between partial payments
        dates.append(dates[-1] + timedelta(days=int(gap)))
    return dates
```

## 4.6 Payment Modes

```python
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
    rng: numpy.random.Generator,
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
    probs = numpy.array(list(weights.values()))
    probs /= probs.sum()
    return rng.choice(modes, p=probs)
```

## 4.7 Invoice Status Update

After generating all payments for an invoice:

```python
def compute_invoice_status(
    invoice_amount: float,
    total_paid: float,
    due_date: date,
    reference_date: date,  # "today" in the simulation
) -> tuple[str, float]:
    """Compute payment_status and balance_due."""

    balance = round(invoice_amount - total_paid, 2)

    if balance <= 0.01:  # Floating point tolerance
        return "paid", 0.0
    elif total_paid > 0:
        if reference_date > due_date:
            return "overdue", balance
        return "partial", balance
    else:
        if reference_date > due_date:
            return "overdue", balance
        return "unpaid", balance
```

## 4.8 Outstanding Balance Enforcement

The `OutstandingSegment` is enforced by adjusting payment probabilities globally:

| Segment | Strategy |
|---------|----------|
| **Fast Clearer** | Pay 95%+ of invoices fully; leave < 5% outstanding |
| **Maintainer** | Keep 20–40% of recent invoices partially/unpaid |
| **High Utilizer** | Keep 70–95% of credit limit utilized at any point |
| **Balanced** | Target 30–50% of credit limit utilization |

The engine tracks running balances per customer and adjusts payment generation to converge toward the target utilization ratio.

## 4.9 Payment Number Format

```
PAY-{YEAR}-{SEQUENCE:06d}

Examples:
  PAY-2024-000001
  PAY-2024-000002
```

## 4.10 Expected Output Volumes

| Customer Type | Avg Payments / Invoice | Total Payments / Customer / Year |
|--------------|----------------------|--------------------------------|
| Hyper/Fast Payer | 1.0–1.1 | ≈ invoice count |
| Moderate Payer | 1.0–1.5 | 1.2× invoice count |
| Delayed Payer | 1.5–2.5 | 2× invoice count |
| Chronic Late | 2.0–4.0 | 3× invoice count (many partial) |

For 100,000 sales records, expect approximately **120,000–200,000** payment records.
