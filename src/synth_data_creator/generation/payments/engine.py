from datetime import date
from typing import Any
import numpy as np

from synth_data_creator.generation.customers.profiles import CustomerProfile
from synth_data_creator.generation.customers.segments import PaymentSegment
from synth_data_creator.generation.payments.scheduling import (
    calculate_payment_date,
    compute_invoice_status,
    select_payment_mode,
    split_payment,
    spread_payment_dates,
)

class GlobalPaymentTracker:
    def __init__(self) -> None:
        self.year_sequences: dict[int, int] = {}

    def get_next_payment_number(self, year: int) -> str:
        seq = self.year_sequences.get(year, 0) + 1
        self.year_sequences[year] = seq
        return f"PAY-{year}-{seq:06d}"


def generate_payments_for_customer(
    profile: CustomerProfile,
    sales_records: list[dict[str, Any]],
    payment_tracker: GlobalPaymentTracker,
    end_date: date,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Generate payment records for a customer's sales, updating the sales records in-place."""
    payment_records = []
    
    # Sort sales chronologically by invoice_date
    sorted_sales = sorted(sales_records, key=lambda s: s["invoice_date"])

    running_outstanding = 0.0

    for sale in sorted_sales:
        invoice_amount = sale["invoice_amount"]
        due_date = sale["due_date"]
        invoice_date = sale["invoice_date"]
        
        # Outstanding Balance enforcement checks
        # If Fast Clearer: very high probability of paying
        # If High Utilizer: might skip payments if under limit, but if they exceed limit, they pay
        will_pay = True
        if profile.payment_segment == PaymentSegment.CHRONIC_LATE:
            # Chronic Late: 15% chance of complete non-payment (stays unpaid)
            if rng.random() < 0.15:
                will_pay = False

        if not will_pay:
            # Update status as unpaid/overdue
            status, balance = compute_invoice_status(invoice_amount, 0.0, due_date, end_date)
            sale["amount_paid"] = 0.0
            sale["balance_due"] = balance
            sale["payment_status"] = status
            running_outstanding += balance
            continue

        # Full or partial?
        is_full = rng.random() < profile.full_payment_probability
        
        # Adjust splits based on profile
        if is_full or profile.max_payment_splits < 2:
            num_splits = 1
        else:
            num_splits = int(rng.integers(2, profile.max_payment_splits + 1))

        # Split amounts
        amounts = split_payment(invoice_amount, num_splits, rng)

        # Spread dates
        first_date = calculate_payment_date(invoice_date, profile, rng)
        payment_dates = spread_payment_dates(first_date, num_splits, rng)

        total_paid_before_end = 0.0

        for amt, p_date in zip(amounts, payment_dates):
            # Only record the payment if it happened on or before the end date of the simulation
            if p_date <= end_date:
                total_paid_before_end = round(total_paid_before_end + amt, 2)
                p_num = payment_tracker.get_next_payment_number(p_date.year)
                p_mode = select_payment_mode(amt, rng)
                
                # UTR or reference number
                ref_num = f"REF-{p_date.year}-{int(rng.integers(100000, 999999))}"

                payment_records.append({
                    "customer_id": profile.id,
                    "invoice_id": sale["id"] if "id" in sale else None,  # Will be mapped to SQLAlchemy model PK
                    "payment_number": p_num,
                    "payment_date": p_date,
                    "payment_amount": amt,
                    "payment_mode": p_mode,
                    "reference_number": ref_num,
                    "remarks": f"Invoice payment for {sale['invoice_number']}",
                    "sale_invoice_number": sale["invoice_number"], # Temporary key to associate post-insert
                })

        # Update the sale record details
        status, balance = compute_invoice_status(invoice_amount, total_paid_before_end, due_date, end_date)
        sale["amount_paid"] = total_paid_before_end
        sale["balance_due"] = balance
        sale["payment_status"] = status
        running_outstanding += balance

    return payment_records
