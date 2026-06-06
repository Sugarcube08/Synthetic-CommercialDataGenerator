from datetime import date
import numpy as np

from synth_data_creator.generation.customers.segments import VolumeSegment

def calculate_discount_pct(
    volume_segment: VolumeSegment,
    quantity: int,
    registration_date: date,
    order_date: date,
    rng: np.random.Generator,
) -> float:
    """Calculate discount percentage based on segment, quantity, and loyalty."""
    # Base segment discount
    if volume_segment == VolumeSegment.WHALE:
        base_disc = rng.uniform(8.0, 15.0)
    elif volume_segment == VolumeSegment.MEDIUM:
        base_disc = rng.uniform(3.0, 8.0)
    else:  # SMALL
        base_disc = rng.uniform(0.0, 3.0)

    # Bulk bonus (> 100 units)
    bulk_bonus = rng.uniform(2.0, 5.0) if quantity > 100 else 0.0

    # Loyalty bonus (> 12 months since registration)
    loyalty_days = (order_date - registration_date).days
    loyalty_bonus = rng.uniform(1.0, 3.0) if loyalty_days > 365 else 0.0

    total_discount = base_disc + bulk_bonus + loyalty_bonus
    # Clamp to max 90% discount for sanity
    return min(90.0, max(0.0, total_discount))


def calculate_gst(
    taxable_amount: float,
    customer_state: str,
    seller_state: str = "MH",  # Maharashtra default
    product_category: str = "general",
) -> dict[str, float]:
    """Calculate GST based on inter/intra-state rules."""
    rates = {
        "Electronics": 18.0,
        "FMCG": 12.0,
        "Hardware": 18.0,
        "Textiles": 5.0,
        "Pharmaceuticals": 12.0,
        "Stationery": 18.0,
    }
    rate = rates.get(product_category, 18.0)

    # Clean inputs to avoid whitespace mismatches
    c_state = customer_state.strip().upper() if customer_state else ""
    s_state = seller_state.strip().upper() if seller_state else ""

    if c_state == s_state or not c_state:
        # Intra-state: split into CGST + SGST
        half_rate = rate / 2
        cgst = round(taxable_amount * half_rate / 100, 2)
        sgst = round(taxable_amount * half_rate / 100, 2)
        return {"cgst": cgst, "sgst": sgst, "igst": 0.0, "rate": rate}
    else:
        # Inter-state: IGST
        igst = round(taxable_amount * rate / 100, 2)
        return {"cgst": 0.0, "sgst": 0.0, "igst": igst, "rate": rate}
