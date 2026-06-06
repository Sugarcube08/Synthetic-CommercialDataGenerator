from datetime import date, timedelta
from typing import Any
import uuid
import numpy as np

from synth_data_creator.generation.customers.profiles import CustomerProfile
from synth_data_creator.generation.customers.segments import FrequencySegment, LifecycleSegment, VolumeSegment

from synth_data_creator.generation.sales.pricing import calculate_discount_pct, calculate_gst
from synth_data_creator.generation.sales.products import pick_product

class GlobalInvoiceTracker:
    def __init__(self) -> None:
        self.year_sequences: dict[int, int] = {}

    def get_next_invoice_number(self, year: int) -> str:
        seq = self.year_sequences.get(year, 0) + 1
        self.year_sequences[year] = seq
        return f"INV-{year}-{seq:06d}"


def get_lifecycle_modifier(
    profile: CustomerProfile,
    current_date: date,
    start_date: date,
    end_date: date,
) -> float:
    """Return probability multiplier based on lifecycle position."""
    total_days = (end_date - start_date).days
    if total_days <= 0:
        return 1.0
        
    progress = (current_date - start_date).days / total_days
    progress = max(0.0, min(progress, 1.0))

    if profile.lifecycle_segment == LifecycleSegment.GROWING:
        return float(0.6 + (0.4 * progress))  # Ramps up
    elif profile.lifecycle_segment == LifecycleSegment.STABLE:
        return 0.9  # Constant
    elif profile.lifecycle_segment == LifecycleSegment.DECLINING:
        return float(max(0.0, 1.0 - (0.5 * progress)))  # Ramps down
    elif profile.lifecycle_segment == LifecycleSegment.CHURN_RISK:
        if progress > profile.churn_active_ratio:
            return 0.02  # Nearly zero after churn point
        return 0.8
    else:
        return 1.0


def apply_seasonality(
    dates: list[date],
    profile: CustomerProfile,
    rng: np.random.Generator,
) -> list[date]:
    """Filter/amplify dates based on seasonal pattern."""
    if profile.frequency_segment != FrequencySegment.SEASONAL:
        return dates

    result = []
    for d in dates:
        if d.month in profile.seasonal_peak_months:
            # Keep and potentially duplicate orders in peak months
            result.append(d)
            if rng.random() < 0.4:  # Extra orders in peak
                result.append(d + timedelta(days=int(rng.integers(1, 5))))
        else:
            # Reduced orders in trough months
            if rng.random() < profile.seasonal_trough_multiplier:
                result.append(d)
    return sorted(result)


def generate_order_dates(
    profile: CustomerProfile,
    start_date: date,
    end_date: date,
    rng: np.random.Generator,
) -> list[date]:
    """Generate order dates based on customer frequency profile."""
    dates = []
    current = profile.registration_date

    while current < end_date:
        # Sample inter-order interval from profile distribution
        # Clamp std to avoid division by zero or negative std
        std = max(1.0, profile.order_frequency_std)
        interval = max(1, int(rng.normal(profile.order_frequency_days, std)))
        current += timedelta(days=interval)

        if current < end_date:
            # Apply lifecycle modifier
            modifier = get_lifecycle_modifier(profile, current, start_date, end_date)
            if rng.random() < modifier:
                dates.append(current)

    # Apply seasonality if seasonal buyer
    dates = apply_seasonality(dates, profile, rng)
    return dates


def generate_sales_for_customer(
    profile: CustomerProfile,
    order_dates: list[date],
    invoice_tracker: GlobalInvoiceTracker,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Generate sales records for a single customer across their order dates."""
    records = []

    for order_date in order_dates:
        # Determine invoice dates (0 to 2 days after order date)
        invoice_date = order_date + timedelta(days=int(rng.integers(0, 3)))
        due_date = invoice_date + timedelta(days=profile.payment_terms_days)
        invoice_number = invoice_tracker.get_next_invoice_number(invoice_date.year)

        # Number of line items per order
        num_items = max(1, int(rng.poisson(profile.items_per_order)))

        for _ in range(num_items):
            category, product_info = pick_product(profile.business_type, rng)
            base_price = product_info["base_price"]
            # Price variation +/- 5%
            unit_price = round(float(base_price * rng.uniform(0.95, 1.05)), 2)

            # Determine quantity based on volume segment
            if profile.volume_segment == VolumeSegment.WHALE:
                quantity = int(rng.integers(100, 5001))
            elif profile.volume_segment == VolumeSegment.MEDIUM:
                quantity = int(rng.integers(20, 501))
            else:  # SMALL
                quantity = int(rng.integers(1, 51))

            gross_amount = round(quantity * unit_price, 2)
            discount_pct = round(calculate_discount_pct(
                profile.volume_segment,
                quantity,
                profile.registration_date,
                order_date,
                rng,
            ), 2)
            discount_amount = round(gross_amount * (discount_pct / 100.0), 2)
            taxable_amount = round(gross_amount - discount_amount, 2)

            # Calculate GST
            gst = calculate_gst(taxable_amount, profile.state, product_category=category)
            cgst = gst["cgst"]
            sgst = gst["sgst"]
            igst = gst["igst"]
            total_tax = round(cgst + sgst + igst, 2)
            invoice_amount = round(taxable_amount + total_tax, 2)

            records.append({
                "id": uuid.uuid4(),
                "customer_id": profile.id,
                "invoice_number": invoice_number,
                "order_date": order_date,
                "invoice_date": invoice_date,
                "due_date": due_date,
                "product_category": category,
                "product_name": product_info["name"],
                "quantity": quantity,
                "unit_price": unit_price,
                "gross_amount": gross_amount,
                "discount_pct": round(discount_pct, 2),
                "discount_amount": discount_amount,
                "taxable_amount": taxable_amount,
                "tax_rate": gst["rate"],
                "cgst_amount": cgst,
                "sgst_amount": sgst,
                "igst_amount": igst,
                "total_tax": total_tax,
                "invoice_amount": invoice_amount,
                "payment_terms_days": profile.payment_terms_days,
                "amount_paid": 0.0,
                "balance_due": invoice_amount,
                "payment_status": "unpaid",
            })

    return records
