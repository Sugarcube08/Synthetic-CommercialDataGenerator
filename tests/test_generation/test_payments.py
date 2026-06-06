from datetime import date
import numpy as np

from synth_data_creator.generation.customers.profiles import CustomerProfile
from synth_data_creator.generation.sales.engine import (
    GlobalInvoiceTracker,
    generate_order_dates,
    generate_sales_for_customer,
)
from synth_data_creator.generation.payments.engine import (
    GlobalPaymentTracker,
    generate_payments_for_customer,
)

def test_payment_generation(seeded_rng: np.random.Generator, sample_profiles: list[CustomerProfile]) -> None:
    """Verify generated payments sum properly and respect invoice constraints."""
    inv_tracker = GlobalInvoiceTracker()
    pay_tracker = GlobalPaymentTracker()
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)

    for profile in sample_profiles:
        dates = generate_order_dates(profile, start, end, seeded_rng)
        sales = generate_sales_for_customer(profile, dates, inv_tracker, seeded_rng)
        
        # Keep copy of original invoice amounts
        original_amounts = {s["invoice_number"]: s["invoice_amount"] for s in sales}
        
        # Generate payments
        payments = generate_payments_for_customer(profile, sales, pay_tracker, end, seeded_rng)

        # 1. Verify payment references
        for pay in payments:
            assert pay["sale_invoice_number"] in original_amounts
            assert pay["payment_amount"] > 0
            assert pay["payment_date"] <= end

        # 2. Verify payment balances
        # Group payments by invoice_id
        grouped_pays = {}
        for pay in payments:
            inv_id = pay["invoice_id"]
            grouped_pays[inv_id] = grouped_pays.get(inv_id, 0.0) + pay["payment_amount"]

        for sale in sales:
            inv_id = sale["id"]
            total_paid = round(grouped_pays.get(inv_id, 0.0), 2)
            
            assert sale["amount_paid"] == total_paid
            assert sale["balance_due"] == round(sale["invoice_amount"] - total_paid, 2)
            
            if sale["balance_due"] == 0:
                assert sale["payment_status"] == "paid"
            elif sale["amount_paid"] > 0:
                assert sale["payment_status"] in ("partial", "overdue")
            else:
                assert sale["payment_status"] in ("unpaid", "overdue")
