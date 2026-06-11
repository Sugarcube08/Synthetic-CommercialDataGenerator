from dataclasses import dataclass
from datetime import date

@dataclass
class GlobalEvent:
    name: str
    description: str
    start_date: date | None = None  # None for annual recurring
    end_date: date | None = None    # None for annual recurring
    start_month: int | None = None  # For recurring (e.g., 10 for October)
    start_day: int | None = None
    end_month: int | None = None    # For recurring
    end_day: int | None = None
    
    # Modifiers
    quantity_mult: float = 1.0
    price_mult: float = 1.0
    discount_add: float = 0.0      # E.g., +5% discount
    frequency_mult: float = 1.0    # < 1.0 means more frequent
    delay_mult: float = 1.0        # > 1.0 means slower payment
    full_pay_mult: float = 1.0     # < 1.0 means less full payment
    return_mult: float = 1.0       # > 1.0 means more returns
    
    # Filtering
    applicable_business_types: list[str] | None = None


GLOBAL_EVENTS = [
    # Recurring: Festival Season (Diwali Peak) - Oct 1 to Nov 15
    GlobalEvent(
        name="Festival Season (Diwali Peak)",
        description="Massive retail and wholesale demand during Indian festive season.",
        start_month=10, start_day=1,
        end_month=11, end_day=15,
        quantity_mult=1.4,
        frequency_mult=0.6,  # 40% more frequent orders
        discount_add=5.0,    # extra 5% discount
        delay_mult=0.9,      # payments slightly faster
        applicable_business_types=["retailer", "wholesaler"]
    ),
    # Recurring: Holiday Shopping Surge - Dec 20 to Jan 5
    GlobalEvent(
        name="Holiday Shopping Surge",
        description="Increased consumer demand and inventory clearance.",
        start_month=12, start_day=20,
        end_month=1, end_day=5,
        quantity_mult=1.25,
        frequency_mult=0.75,
        discount_add=8.0,    # extra 8% discount
        applicable_business_types=["retailer", "wholesaler", "distributor"]
    ),
    # Recurring: Fiscal Year Closing Rush - March 15 to March 31
    GlobalEvent(
        name="Fiscal Year Close Rush",
        description="Organizations clearing inventory and budget spending.",
        start_month=3, start_day=15,
        end_month=3, end_day=31,
        quantity_mult=1.3,
        frequency_mult=0.7,
        delay_mult=0.7,      # clear outstanding invoices before books close
        full_pay_mult=1.2,
        applicable_business_types=["manufacturer", "wholesaler", "distributor"]
    ),
    # Specific: 2020 COVID Lockdown & Supply Shock - March 20, 2020 to Aug 31, 2020
    GlobalEvent(
        name="COVID Lockdown & Supply Shock",
        description="Severe logistics disruption, retail halts, healthcare surge.",
        start_date=date(2020, 3, 20),
        end_date=date(2020, 8, 31),
        quantity_mult=0.5,      # 50% drop in normal goods
        price_mult=1.1,         # price hikes due to scarcity
        frequency_mult=2.0,     # orders half as frequent
        delay_mult=1.8,         # severe cash crunch, delayed payments
        full_pay_mult=0.4,      # partial payments dominate
        return_mult=1.5,        # supply mismatch returns
    ),
    # Specific: 2021-2022 Global Supply Chain Crisis - June 1, 2021 to June 1, 2022
    GlobalEvent(
        name="Supply Chain Crisis",
        description="Material shortages, shipping delays, industrial inflation.",
        start_date=date(2021, 6, 1),
        end_date=date(2022, 6, 1),
        quantity_mult=0.8,
        price_mult=1.15,        # 15% price inflation
        delay_mult=1.2,
        return_mult=1.3         # quality issues from substitute materials
    ),
    # Specific: 2023 Macroeconomic Downturn / Inflation Surge - Jan 1, 2023 to Oct 31, 2023
    GlobalEvent(
        name="Macroeconomic Downturn",
        description="High inflation, reduced consumer spending, cash preservation.",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 10, 31),
        quantity_mult=0.85,
        frequency_mult=1.2,
        delay_mult=1.4,         # customers delaying payment to preserve cash
        full_pay_mult=0.6,
    )
]


def get_active_events(d: date, business_type: str | None = None) -> list[GlobalEvent]:
    """Identify which events are active on a given date for a business type."""
    active = []
    for event in GLOBAL_EVENTS:
        # Check applicability
        if business_type and event.applicable_business_types:
            if business_type not in event.applicable_business_types:
                continue
                
        # Check date bounds
        is_active = False
        if event.start_date and event.end_date:
            if event.start_date <= d <= event.end_date:
                is_active = True
        elif event.start_month and event.end_month:
            # Recurring event (handling wrapping over Dec-Jan)
            m = d.month
            day = d.day
            
            start_val = (event.start_month, event.start_day or 1)
            end_val = (event.end_month, event.end_day or 28)
            curr_val = (m, day)
            
            if event.start_month <= event.end_month:
                if start_val <= curr_val <= end_val:
                    is_active = True
            else:
                # Dec-Jan wrapping
                if curr_val >= start_val or curr_val <= end_val:
                    is_active = True
                    
        if is_active:
            active.append(event)
    return active


def get_event_modifiers(d: date, business_type: str) -> dict[str, float]:
    """Combine multipliers of all active events on a date for a business type."""
    events = get_active_events(d, business_type)
    
    qty_m = 1.0
    price_m = 1.0
    disc_add = 0.0
    freq_m = 1.0
    delay_m = 1.0
    full_pay_m = 1.0
    ret_m = 1.0
    
    for ev in events:
        qty_m *= ev.quantity_mult
        price_m *= ev.price_mult
        disc_add += ev.discount_add
        freq_m *= ev.frequency_mult
        delay_m *= ev.delay_mult
        full_pay_m *= ev.full_pay_mult
        ret_m *= ev.return_mult
        
    return {
        "quantity_mult": qty_m,
        "price_mult": price_m,
        "discount_add": disc_add,
        "frequency_mult": freq_m,
        "delay_mult": delay_m,
        "full_pay_mult": full_pay_m,
        "return_mult": ret_m,
    }
