from datetime import date, timedelta
from typing import Any
import numpy as np

from synth_data_creator.generation.customers.profiles import CustomerProfile
from synth_data_creator.generation.customers.segments import DisciplineSegment
from synth_data_creator.generation.returns.reasons import (
    CATEGORY_MULTIPLIERS,
    REASON_WEIGHTS,
    ReturnReason,
)

class GlobalReturnTracker:
    def __init__(self) -> None:
        self.return_sequences: dict[int, int] = {}
        self.cn_sequences: dict[int, int] = {}

    def get_next_return_number(self, year: int) -> str:
        seq = self.return_sequences.get(year, 0) + 1
        self.return_sequences[year] = seq
        return f"RET-{year}-{seq:06d}"

    def get_next_credit_note_number(self, year: int) -> str:
        seq = self.cn_sequences.get(year, 0) + 1
        self.cn_sequences[year] = seq
        return f"CN-{year}-{seq:06d}"


def determine_return_quantity(
    original_quantity: int,
    reason: ReturnReason,
    rng: np.random.Generator,
) -> int:
    """Determine how many units are returned."""
    if reason in (ReturnReason.WRONG_PRODUCT, ReturnReason.EXPIRED_PRODUCT):
        # Full return
        return original_quantity

    if reason == ReturnReason.DAMAGED_GOODS:
        # Partial: 10–50% of original quantity
        ratio = rng.uniform(0.1, 0.5)
    elif reason == ReturnReason.EXCESS_INVENTORY:
        # Partial: 20–80% of original
        ratio = rng.uniform(0.2, 0.8)
    else:
        # Variable: 10–100%
        ratio = rng.uniform(0.1, 1.0)

    return max(1, int(original_quantity * ratio))


def calculate_return_value(
    quantity_returned: int,
    unit_price: float,
    discount_pct: float,
    tax_rate: float,
) -> dict[str, float]:
    """Calculate the financial impact of a return."""
    gross = quantity_returned * unit_price
    discount = gross * (discount_pct / 100.0)
    taxable = gross - discount
    tax = taxable * (tax_rate / 100.0)

    return_value = round(taxable + tax, 2)
    return {
        "return_value": return_value,
        "credit_note_amount": return_value,
    }


def generate_return_date(
    invoice_date: date,
    reason: ReturnReason,
    rng: np.random.Generator,
) -> date:
    """Generate a realistic return date based on reason."""
    delay_ranges = {
        ReturnReason.DAMAGED_GOODS: (1, 7),        # Found immediately
        ReturnReason.DELIVERY_ISSUES: (0, 3),      # At delivery
        ReturnReason.QUALITY_DEFECT: (3, 30),      # Found during use
        ReturnReason.WRONG_PRODUCT: (1, 5),        # Quick identification
        ReturnReason.EXCESS_INVENTORY: (30, 90),   # End of season
        ReturnReason.CUSTOMER_DISSATISFACTION: (7, 45),
        ReturnReason.EXPIRED_PRODUCT: (14, 60),
        ReturnReason.PRICING_DISPUTE: (1, 14),
    }

    min_days, max_days = delay_ranges[reason]
    delay = rng.integers(min_days, max_days + 1)
    return invoice_date + timedelta(days=int(delay))


def generate_returns_for_customer(
    profile: CustomerProfile,
    sales_records: list[dict[str, Any]],
    return_tracker: GlobalReturnTracker,
    end_date: date,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Generate return records linked to the customer's sales."""
    return_records = []

    discipline_multipliers = {
        DisciplineSegment.DISCIPLINED: 0.5,
        DisciplineSegment.MODERATE: 1.0,
        DisciplineSegment.UNDISCIPLINED: 2.0,
    }
    discipline_mult = discipline_multipliers.get(profile.discipline_segment, 1.0)

    for sale in sales_records:
        category = sale["product_category"]
        cat_mult = CATEGORY_MULTIPLIERS.get(category, 1.0)
        
        # Effective return probability
        effective_rate = profile.return_probability * cat_mult * discipline_mult

        if rng.random() < effective_rate:
            # Pick reason based on weights
            reason_probs = REASON_WEIGHTS.get(category, {})
            if not reason_probs:
                reason = ReturnReason(rng.choice([r.value for r in ReturnReason]))
            else:
                reasons_list = list(reason_probs.keys())
                weights = np.array(list(reason_probs.values()))
                weights /= weights.sum()
                reason = ReturnReason(rng.choice([r.value for r in reasons_list], p=weights))


            # Determine return date
            invoice_date = sale["invoice_date"]
            ret_date = generate_return_date(invoice_date, reason, rng)

            # Return date must be within date range
            if ret_date <= end_date:
                qty_ret = determine_return_quantity(sale["quantity"], reason, rng)
                fin = calculate_return_value(
                    qty_ret,
                    sale["unit_price"],
                    sale["discount_pct"],
                    sale["tax_rate"],
                )

                # Return status workflow: 90% approved, 10% rejected
                # If approved: 95% credited
                status_roll = rng.random()
                if status_roll < 0.90:
                    credited_roll = rng.random()
                    if credited_roll < 0.95:
                        status = "credited"
                        cn_num = return_tracker.get_next_credit_note_number(ret_date.year)
                        cn_amt = fin["credit_note_amount"]
                    else:
                        status = "approved"
                        cn_num = None
                        cn_amt = 0.0
                else:
                    status = "rejected"
                    cn_num = None
                    cn_amt = 0.0
                    
                # We can also have pending returns
                if rng.random() < 0.05 and status == "approved":
                    status = "pending"
                    cn_num = None
                    cn_amt = 0.0

                ret_num = return_tracker.get_next_return_number(ret_date.year)

                return_records.append({
                    "customer_id": profile.id,
                    "sale_id": sale["id"] if "id" in sale else None,
                    "return_number": ret_num,
                    "return_date": ret_date,
                    "return_reason": reason.value,
                    "quantity_returned": qty_ret,
                    "return_value": fin["return_value"],
                    "credit_note_number": cn_num,
                    "credit_note_amount": cn_amt,
                    "status": status,
                    "remarks": f"Return for invoice line: {sale['invoice_number']}",
                    "sale_invoice_number": sale["invoice_number"], # Temporary association key
                })

    return return_records
