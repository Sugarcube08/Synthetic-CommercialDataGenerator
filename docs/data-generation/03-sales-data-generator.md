# 03 — Sales Data Generator

## 3.1 Overview

The Sales Engine generates `raw_sales` records for each customer, driven entirely by their `CustomerProfile`. Each record represents a single invoice line item (one product per row), though multiple rows can share the same `invoice_number` to simulate multi-item orders.

## 3.2 Generation Pipeline

```
Input: CustomerProfile, date_range, rng
                │
                ▼
┌──────────────────────────────┐
│ 1. Generate Order Timeline   │ ← Frequency segment → order dates
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ 2. Apply Lifecycle Modifiers │ ← Growth/decline adjustments
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ 3. Apply Seasonality         │ ← Seasonal buyers' peak/trough
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ 4. For Each Order:           │
│    a. Select products        │ ← Category + product selection
│    b. Determine quantities   │ ← Volume segment drives range
│    c. Calculate pricing      │ ← Base price + discounts
│    d. Apply taxes            │ ← GST calculation
│    e. Set payment terms      │ ← Profile-driven due dates
└──────────┬───────────────────┘
           │
           ▼
       List[SalesRecord]
```

## 3.3 Order Timeline Generation

### Step 1: Base Frequency

```python
def generate_order_dates(
    profile: CustomerProfile,
    start_date: date,
    end_date: date,
    rng: numpy.random.Generator,
) -> list[date]:
    """Generate order dates based on customer frequency profile."""

    dates = []
    current = profile.registration_date

    while current < end_date:
        # Sample inter-order interval from profile distribution
        interval = max(1, int(rng.normal(
            profile.order_frequency_days,
            profile.order_frequency_std * profile.discipline_cv
        )))
        current += timedelta(days=interval)

        if current < end_date:
            # Apply lifecycle modifier
            modifier = get_lifecycle_modifier(profile, current, start_date, end_date)
            if rng.random() < modifier:
                dates.append(current)

    return dates
```

### Step 2: Lifecycle Volume Modifier

```python
def get_lifecycle_modifier(
    profile: CustomerProfile,
    current_date: date,
    start_date: date,
    end_date: date,
) -> float:
    """Return probability multiplier based on lifecycle position."""
    progress = (current_date - start_date).days / (end_date - start_date).days

    match profile.lifecycle_segment:
        case LifecycleSegment.GROWING:
            return 0.6 + (0.4 * progress)  # Ramps up
        case LifecycleSegment.STABLE:
            return 0.9  # Constant
        case LifecycleSegment.DECLINING:
            return 1.0 - (0.5 * progress)  # Ramps down
        case LifecycleSegment.CHURN_RISK:
            if progress > profile.churn_active_ratio:
                return 0.02  # Nearly zero after churn point
            return 0.8
```

### Step 3: Seasonality Filter

```python
def apply_seasonality(
    dates: list[date],
    profile: CustomerProfile,
    rng: numpy.random.Generator,
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
                result.append(d + timedelta(days=rng.integers(1, 5)))
        else:
            # Reduced orders in trough months
            if rng.random() < profile.seasonal_trough_multiplier:
                result.append(d)
    return sorted(result)
```

## 3.4 Product Catalog

A static product catalog provides realistic wholesale product data:

```python
PRODUCT_CATALOG = {
    "Electronics": [
        {"name": "LED Panel 40W", "base_price": 850.00, "unit": "piece"},
        {"name": "USB-C Cable 1m", "base_price": 120.00, "unit": "piece"},
        {"name": "Power Adapter 65W", "base_price": 450.00, "unit": "piece"},
        {"name": "Bluetooth Speaker", "base_price": 1200.00, "unit": "piece"},
        {"name": "Smart Plug WiFi", "base_price": 680.00, "unit": "piece"},
    ],
    "FMCG": [
        {"name": "Detergent Powder 5kg", "base_price": 280.00, "unit": "pack"},
        {"name": "Cooking Oil 5L", "base_price": 520.00, "unit": "can"},
        {"name": "Rice Basmati 25kg", "base_price": 1800.00, "unit": "bag"},
        {"name": "Sugar 50kg", "base_price": 2100.00, "unit": "bag"},
        {"name": "Tea Powder 1kg", "base_price": 350.00, "unit": "pack"},
    ],
    "Hardware": [
        {"name": "PVC Pipe 4inch 6ft", "base_price": 320.00, "unit": "piece"},
        {"name": "Cement 50kg", "base_price": 380.00, "unit": "bag"},
        {"name": "Steel Rod 12mm", "base_price": 550.00, "unit": "piece"},
        {"name": "Paint Emulsion 20L", "base_price": 2800.00, "unit": "bucket"},
        {"name": "Electrical Wire 90m", "base_price": 1500.00, "unit": "roll"},
    ],
    "Textiles": [
        {"name": "Cotton Fabric 100m", "base_price": 4500.00, "unit": "roll"},
        {"name": "Polyester Blend 50m", "base_price": 2200.00, "unit": "roll"},
        {"name": "Denim Fabric 50m", "base_price": 3500.00, "unit": "roll"},
    ],
    "Pharmaceuticals": [
        {"name": "Paracetamol 500mg (100s)", "base_price": 45.00, "unit": "strip"},
        {"name": "Sanitizer 5L", "base_price": 350.00, "unit": "can"},
        {"name": "Surgical Mask (50s)", "base_price": 180.00, "unit": "box"},
    ],
    "Stationery": [
        {"name": "A4 Paper Ream 500", "base_price": 280.00, "unit": "ream"},
        {"name": "Printer Ink Cartridge", "base_price": 650.00, "unit": "piece"},
        {"name": "Notebook 200pg (dozen)", "base_price": 480.00, "unit": "dozen"},
    ],
}
```

**Product selection** is weighted by customer business type and volume segment.

## 3.5 Pricing Model

### Discount Tiers

| Condition | Discount Range |
|-----------|---------------|
| Whale customer | 8–15% |
| Medium customer | 3–8% |
| Small customer | 0–3% |
| Bulk quantity bonus (>100 units) | Additional 2–5% |
| Loyalty (>12 months active) | Additional 1–3% |

### Tax Calculation (Indian GST)

```python
def calculate_gst(
    taxable_amount: float,
    customer_state: str,
    seller_state: str = "MH",  # Maharashtra default
    product_category: str = "general",
) -> dict:
    """Calculate GST based on inter/intra-state rules."""

    # GST rates by category
    rates = {
        "Electronics": 18.0,
        "FMCG": 12.0,
        "Hardware": 18.0,
        "Textiles": 5.0,
        "Pharmaceuticals": 12.0,
        "Stationery": 18.0,
    }
    rate = rates.get(product_category, 18.0)

    if customer_state == seller_state:
        # Intra-state: split into CGST + SGST
        half_rate = rate / 2
        cgst = round(taxable_amount * half_rate / 100, 2)
        sgst = round(taxable_amount * half_rate / 100, 2)
        return {"cgst": cgst, "sgst": sgst, "igst": 0, "rate": rate}
    else:
        # Inter-state: IGST
        igst = round(taxable_amount * rate / 100, 2)
        return {"cgst": 0, "sgst": 0, "igst": igst, "rate": rate}
```

## 3.6 Invoice Number Format

```
INV-{YEAR}-{SEQUENCE:06d}

Examples:
  INV-2024-000001
  INV-2024-000002
  INV-2025-000001  (resets annually)
```

Sequence numbers are assigned globally in chronological order to maintain realistic numbering.

## 3.7 Financial Integrity Rules

Every sales record MUST satisfy:

```
gross_amount    = quantity × unit_price
discount_amount = gross_amount × discount_pct / 100
taxable_amount  = gross_amount − discount_amount
total_tax       = cgst_amount + sgst_amount + igst_amount
invoice_amount  = taxable_amount + total_tax
balance_due     = invoice_amount − amount_paid  (initially = invoice_amount)
```

These invariants are checked during generation and enforced via SQL CHECK constraints.

## 3.8 Expected Output Volumes

| Customer Segment | Avg Invoices / Customer / Year |
|-----------------|-------------------------------|
| Whale + Frequent | 150–250 |
| Medium + Occasional | 15–30 |
| Small + Rare | 1–5 |
| Any + Seasonal | 20–60 (concentrated) |

For 1,000 customers over 24 months, expect approximately **60,000–120,000** sales records.
