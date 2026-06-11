from datetime import date
from synth_data_creator.generation.events import get_active_events, get_event_modifiers

def test_covid_lockdown_event() -> None:
    """Verify that COVID Lockdown events are correctly identified and return proper multipliers."""
    # Active COVID lockdown period
    d = date(2020, 5, 1)
    active_events = get_active_events(d)
    
    assert len(active_events) == 1
    assert active_events[0].name == "COVID Lockdown & Supply Shock"
    
    # Check modifiers
    mods = get_event_modifiers(d, "retailer")
    assert mods["quantity_mult"] == 0.5
    assert mods["price_mult"] == 1.1
    assert mods["delay_mult"] == 1.8


def test_recurring_diwali_peak() -> None:
    """Verify that the recurring annual Diwali peak applies correctly only to applicable business types."""
    # October 15 is during the Diwali Peak
    d = date(2025, 10, 15)
    
    # Retailers should receive Diwali peak modifiers
    retail_mods = get_event_modifiers(d, "retailer")
    assert retail_mods["quantity_mult"] == 1.4
    assert retail_mods["frequency_mult"] == 0.6
    
    # Manufacturers should NOT receive Diwali modifiers (it's retailer/wholesaler only)
    mfg_mods = get_event_modifiers(d, "manufacturer")
    assert mfg_mods["quantity_mult"] == 1.0
    assert mfg_mods["frequency_mult"] == 1.0


def test_fiscal_year_close_rush() -> None:
    """Verify that the fiscal year closing rush applies correctly in late March."""
    d = date(2024, 3, 20)
    
    # Wholesalers should get it
    mods = get_event_modifiers(d, "wholesaler")
    assert mods["quantity_mult"] == 1.3
    assert mods["delay_mult"] == 0.7  # Faster payments
