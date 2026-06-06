from datetime import date
import numpy as np

from synth_data_creator.generation.customers.profiles import CustomerProfile
from synth_data_creator.generation.sales.engine import (
    GlobalInvoiceTracker,
    generate_order_dates,
    generate_sales_for_customer,
)
from synth_data_creator.generation.sales.pricing import calculate_gst

def test_financial_integrity(seeded_rng: np.random.Generator, sample_profiles: list[CustomerProfile]) -> None:
    """Verify B2B invoice math holds true for all records."""
    tracker = GlobalInvoiceTracker()
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)

    for profile in sample_profiles:
        dates = generate_order_dates(profile, start, end, seeded_rng)
        sales = generate_sales_for_customer(profile, dates, tracker, seeded_rng)
        
        for sale in sales:
            gross = round(sale["quantity"] * sale["unit_price"], 2)
            assert sale["gross_amount"] == gross

            disc_amt = round(gross * (sale["discount_pct"] / 100.0), 2)
            assert sale["discount_amount"] == disc_amt

            taxable = round(gross - disc_amt, 2)
            assert sale["taxable_amount"] == taxable

            total_tax = round(sale["cgst_amount"] + sale["sgst_amount"] + sale["igst_amount"], 2)
            assert sale["total_tax"] == total_tax

            assert sale["invoice_amount"] == round(taxable + total_tax, 2)
            assert sale["balance_due"] == sale["invoice_amount"]
            assert sale["amount_paid"] == 0.0
            assert sale["payment_status"] == "unpaid"


def test_gst_intra_state() -> None:
    """Verify GST is split into CGST and SGST for same-state, and IGST is zero."""
    res = calculate_gst(1000.0, customer_state="MH", seller_state="MH", product_category="Electronics")
    assert res["rate"] == 18.0
    assert res["cgst"] == 90.0
    assert res["sgst"] == 90.0
    assert res["igst"] == 0.0


def test_gst_inter_state() -> None:
    """Verify GST routes to IGST for cross-state, and CGST/SGST are zero."""
    res = calculate_gst(1000.0, customer_state="DL", seller_state="MH", product_category="Electronics")
    assert res["rate"] == 18.0
    assert res["cgst"] == 0.0
    assert res["sgst"] == 0.0
    assert res["igst"] == 180.0
