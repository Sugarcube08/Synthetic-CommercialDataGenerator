from datetime import date
import numpy as np

from synth_data_creator.generation.customers.profiles import CustomerProfile
from synth_data_creator.generation.sales.engine import (
    GlobalInvoiceTracker,
    generate_order_dates,
    generate_sales_for_customer,
)
from synth_data_creator.generation.returns.engine import (
    GlobalReturnTracker,
    generate_returns_for_customer,
)

def test_returns_generation(seeded_rng: np.random.Generator, sample_profiles: list[CustomerProfile]) -> None:
    """Verify generated returns respect referential and logical constraints."""
    inv_tracker = GlobalInvoiceTracker()
    ret_tracker = GlobalReturnTracker()
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)

    for profile in sample_profiles:
        dates = generate_order_dates(profile, start, end, seeded_rng)
        sales = generate_sales_for_customer(profile, dates, inv_tracker, seeded_rng)
        
        # Keep map of invoice details
        sales_map = {s["id"]: s for s in sales}
        
        # Generate returns
        returns = generate_returns_for_customer(profile, sales, ret_tracker, end, seeded_rng)

        for ret in returns:
            sale_id = ret["sale_id"]
            assert sale_id in sales_map
            
            sale = sales_map[sale_id]
            
            # 1. Quantity constraints
            assert 0 < ret["quantity_returned"] <= sale["quantity"]
            
            # 2. Date constraints
            assert ret["return_date"] >= sale["invoice_date"]
            assert ret["return_date"] <= end
            
            # 3. Status checks
            assert ret["status"] in ("pending", "approved", "rejected", "credited")
            
            if ret["status"] == "credited":
                assert ret["credit_note_number"] is not None
                assert ret["credit_note_amount"] == ret["return_value"]
            else:
                assert ret["credit_note_amount"] == 0.0
