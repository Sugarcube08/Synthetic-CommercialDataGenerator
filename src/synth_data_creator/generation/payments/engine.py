from datetime import date, timedelta
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

from synth_data_creator.generation.events import get_event_modifiers

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

    # Precompute cumulative invoiced amount strictly before each date
    invoiced_by_date = {}
    for s in sorted_sales:
        d = s["invoice_date"]
        invoiced_by_date[d] = invoiced_by_date.get(d, 0.0) + s["invoice_amount"]
    
    sorted_dates = sorted(invoiced_by_date.keys())
    prefix_invoiced_before_date = {}
    current_sum = 0.0
    for d in sorted_dates:
        prefix_invoiced_before_date[d] = round(current_sum, 2)
        current_sum += invoiced_by_date[d]

    # Track scheduled payments to evaluate outstanding balance dynamically
    scheduled_payments = []
    payments_by_sale = {}  # sale_id -> list of payment dicts
    payments_by_date = {}  # payment_date -> float (sum of payment amounts)

    for sale in sorted_sales:
        invoice_amount = sale["invoice_amount"]
        due_date = sale["due_date"]
        invoice_date = sale["invoice_date"]
        sale_id = sale.get("id")
        
        # 1. Calculate current outstanding balance as of invoice_date
        def get_outstanding_on(target_date: date) -> float:
            total_invoiced = prefix_invoiced_before_date.get(target_date, 0.0)
            total_paid = sum(amt for d, amt in payments_by_date.items() if d <= target_date)
            return round(total_invoiced - total_paid, 2)

        curr_outstanding = get_outstanding_on(invoice_date)
        
        # 2. Check if new invoice violates credit limit
        excess = round((curr_outstanding + invoice_amount) - profile.credit_limit, 2)
        
        if excess > 0:
            # Credit limit breached!
            # Resolve this based on outstanding_segment
            # Pull forward scheduled payments of previous invoices to invoice_date
            amount_to_clear = excess
            
            future_payments = [
                p_info for p_info in scheduled_payments
                if p_info["payment"]["payment_date"] > invoice_date
            ]
            future_payments.sort(key=lambda x: x["payment"]["payment_date"])
            
            for p_info in future_payments:
                if amount_to_clear <= 0:
                    break
                p_dict = p_info["payment"]
                
                # Update payments_by_date tracking
                old_date = p_dict["payment_date"]
                amt = p_dict["payment_amount"]
                payments_by_date[old_date] = round(payments_by_date.get(old_date, 0.0) - amt, 2)
                payments_by_date[invoice_date] = round(payments_by_date.get(invoice_date, 0.0) + amt, 2)
                
                p_dict["payment_date"] = invoice_date
                p_dict["remarks"] = p_dict.get("remarks", "") + " (Pulled forward to clear credit limit)"
                amount_to_clear -= amt
                
            # If we still have excess, apply forced payment to previous open invoices
            if amount_to_clear > 0.01:
                forced_pay_amt = round(amount_to_clear, 2)
                
                # Apply forced payment to previous open invoices
                for prev_sale in sorted_sales:
                    if prev_sale["invoice_date"] >= invoice_date:
                        break  # Only previous ones
                    
                    prev_paid = 0.0
                    prev_sale_id = prev_sale.get("id")
                    for pay in payments_by_sale.get(prev_sale_id, []):
                        if pay["payment_date"] <= invoice_date:
                            prev_paid += pay["payment_amount"]
                            
                    prev_balance = round(prev_sale["invoice_amount"] - prev_paid, 2)
                    if prev_balance > 0.01:
                        apply_amt = round(min(forced_pay_amt, prev_balance), 2)
                        if apply_amt > 0.01:
                            p_num = payment_tracker.get_next_payment_number(invoice_date.year)
                            p_mode = "bank_transfer"
                            ref_num = f"REF-{invoice_date.year}-{int(rng.integers(100000, 999999))}"
                            
                            pay_rec = {
                                "customer_id": profile.id,
                                "invoice_id": prev_sale_id,
                                "payment_number": p_num,
                                "payment_date": invoice_date,
                                "payment_amount": apply_amt,
                                "payment_mode": p_mode,
                                "reference_number": ref_num,
                                "remarks": f"Forced credit limit clearance payment applied to {prev_sale['invoice_number']}",
                                "sale_invoice_number": prev_sale["invoice_number"],
                            }
                            payment_records.append(pay_rec)
                            scheduled_payments.append({
                                "payment": pay_rec,
                                "sale": prev_sale
                            })
                            payments_by_sale.setdefault(prev_sale_id, []).append(pay_rec)
                            payments_by_date[invoice_date] = round(payments_by_date.get(invoice_date, 0.0) + apply_amt, 2)
                            
                            forced_pay_amt = round(forced_pay_amt - apply_amt, 2)
                            
                # If there's still forced_pay_amt left, we apply it as an advance on the current sale
                if forced_pay_amt > 0.01:
                    apply_amt = round(min(forced_pay_amt, invoice_amount), 2)
                    if apply_amt > 0.01:
                        p_num = payment_tracker.get_next_payment_number(invoice_date.year)
                        p_mode = "bank_transfer"
                        ref_num = f"REF-{invoice_date.year}-{int(rng.integers(100000, 999999))}"
                        
                        pay_rec = {
                            "customer_id": profile.id,
                            "invoice_id": sale_id,
                            "payment_number": p_num,
                            "payment_date": invoice_date,
                            "payment_amount": apply_amt,
                            "payment_mode": p_mode,
                            "reference_number": ref_num,
                            "remarks": f"Advance payment for invoice {sale['invoice_number']} to release credit",
                            "sale_invoice_number": sale["invoice_number"],
                        }
                        payment_records.append(pay_rec)
                        scheduled_payments.append({
                            "payment": pay_rec,
                            "sale": sale
                        })
                        payments_by_sale.setdefault(sale_id, []).append(pay_rec)
                        payments_by_date[invoice_date] = round(payments_by_date.get(invoice_date, 0.0) + apply_amt, 2)
                        
                        invoice_amount = round(invoice_amount - apply_amt, 2)
        
        # 3. Determine payment for the current invoice
        if invoice_amount > 0.01:
            will_pay = True
            if profile.payment_segment == PaymentSegment.CHRONIC_LATE:
                # Chronic Late: 15% chance of complete non-payment (stays unpaid)
                if rng.random() < 0.15:
                    will_pay = False

            if will_pay:
                # Adjust splits based on profile
                mods = get_event_modifiers(invoice_date, profile.business_type)
                full_pay_prob = min(1.0, max(0.0, profile.full_payment_probability * mods["full_pay_mult"]))
                is_full = rng.random() < full_pay_prob

                if is_full or profile.max_payment_splits < 2:
                    num_splits = 1
                else:
                    num_splits = int(rng.integers(2, profile.max_payment_splits + 1))

                # Split amounts
                amounts = split_payment(invoice_amount, num_splits, rng)

                # Spread dates
                first_date = calculate_payment_date(invoice_date, profile, rng)
                payment_dates = spread_payment_dates(first_date, num_splits, rng)

                # Apply outstanding_segment specific logic to current invoice payment dates
                adjusted_payment_dates = []
                for p_date in payment_dates:
                    days_diff = (p_date - invoice_date).days
                    if profile.outstanding_segment.value == "fast_clearer":
                        days_diff = max(1, int(days_diff * 0.75))
                    elif profile.outstanding_segment.value == "high_credit_utilizer":
                        days_diff = int(days_diff * 1.2)
                    adjusted_payment_dates.append(invoice_date + timedelta(days=days_diff))

                for amt, p_date in zip(amounts, adjusted_payment_dates):
                    p_num = payment_tracker.get_next_payment_number(p_date.year)
                    p_mode = select_payment_mode(amt, rng)
                    ref_num = f"REF-{p_date.year}-{int(rng.integers(100000, 999999))}"

                    pay_rec = {
                        "customer_id": profile.id,
                        "invoice_id": sale_id,
                        "payment_number": p_num,
                        "payment_date": p_date,
                        "payment_amount": amt,
                        "payment_mode": p_mode,
                        "reference_number": ref_num,
                        "remarks": f"Invoice payment for {sale['invoice_number']}",
                        "sale_invoice_number": sale["invoice_number"],
                    }
                    payment_records.append(pay_rec)
                    scheduled_payments.append({
                        "payment": pay_rec,
                        "sale": sale
                    })
                    payments_by_sale.setdefault(sale_id, []).append(pay_rec)
                    payments_by_date[p_date] = round(payments_by_date.get(p_date, 0.0) + amt, 2)

    # 4. Filter payment records to only include those on or before end_date,
    # and update the sales records details in place
    final_payment_records = []
    
    # Reset sales status and sum paid amounts
    for sale in sales_records:
        sale["amount_paid"] = 0.0
        sale["balance_due"] = float(sale["invoice_amount"])
        sale["payment_status"] = "unpaid"

    for p_info in scheduled_payments:
        pay = p_info["payment"]
        sale = p_info["sale"]
        if pay["payment_date"] <= end_date:
            final_payment_records.append(pay)
            sale["amount_paid"] = round(sale["amount_paid"] + pay["payment_amount"], 2)

    # Compute status and balance for each sale
    for sale in sales_records:
        invoice_amount = float(sale["invoice_amount"])
        total_paid = float(sale["amount_paid"])
        due_date = sale["due_date"]
        
        status, balance = compute_invoice_status(invoice_amount, total_paid, due_date, end_date)
        sale["amount_paid"] = total_paid
        sale["balance_due"] = balance
        sale["payment_status"] = status

    return final_payment_records
