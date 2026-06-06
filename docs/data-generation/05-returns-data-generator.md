# 05 — Returns Data Generator

## 5.1 Overview

The Returns Engine generates `raw_returns` records linked to existing sales. Return probabilities are driven by the customer's `DisciplineSegment` and product category. Returns simulate realistic wholesale scenarios including damaged goods, delivery issues, and excess inventory.

## 5.2 Generation Pipeline

```
Input: All raw_sales records, CustomerProfiles
                │
                ▼
┌───────────────────────────────────┐
│ 1. For each sale, check if       │
│    a return occurs               │ ← return_probability from profile
└──────────┬────────────────────────┘
           │
           ▼
┌───────────────────────────────────┐
│ 2. Determine return reason       │ ← Weighted random by category
└──────────┬────────────────────────┘
           │
           ▼
┌───────────────────────────────────┐
│ 3. Calculate return quantity     │ ← Partial or full return
└──────────┬────────────────────────┘
           │
           ▼
┌───────────────────────────────────┐
│ 4. Compute return value &        │
│    credit note                   │
└──────────┬────────────────────────┘
           │
           ▼
┌───────────────────────────────────┐
│ 5. Assign return date            │ ← After delivery, before expiry
└──────────┬────────────────────────┘
           │
           ▼
       List[ReturnRecord]
```

## 5.3 Return Probability Model

### Base Return Rate by Discipline

| Discipline Segment | Base Return Rate |
|-------------------|-----------------|
| Disciplined | 2% per invoice |
| Moderate | 5% per invoice |
| Undisciplined | 10% per invoice |

### Category Multipliers

| Product Category | Multiplier | Rationale |
|-----------------|-----------|-----------|
| Electronics | 1.5× | Higher defect/DOA rates |
| FMCG | 0.8× | Low return tolerance, consumables |
| Hardware | 1.2× | Damage in transit |
| Textiles | 1.3× | Color/quality mismatches |
| Pharmaceuticals | 0.5× | Regulated, rarely returned |
| Stationery | 0.7× | Low-value, low return motivation |

### Effective Return Probability

```python
effective_rate = base_rate × category_multiplier × discipline_multiplier
```

Where `discipline_multiplier` comes from:
- Disciplined: 0.5×
- Moderate: 1.0×
- Undisciplined: 2.0×

## 5.4 Return Reason Taxonomy

```python
class ReturnReason(str, Enum):
    DAMAGED_GOODS = "damaged_goods"
    DELIVERY_ISSUES = "delivery_issues"
    QUALITY_DEFECT = "quality_defect"
    WRONG_PRODUCT = "wrong_product"
    EXCESS_INVENTORY = "excess_inventory"
    CUSTOMER_DISSATISFACTION = "customer_dissatisfaction"
    EXPIRED_PRODUCT = "expired_product"
    PRICING_DISPUTE = "pricing_dispute"
```

### Reason Weights by Category

| Reason | Electronics | FMCG | Hardware | Textiles | Pharma | Stationery |
|--------|-----------|------|---------|---------|--------|-----------|
| Damaged goods | 25% | 15% | 35% | 20% | 10% | 10% |
| Delivery issues | 15% | 10% | 25% | 10% | 5% | 10% |
| Quality defect | 30% | 10% | 15% | 30% | 15% | 10% |
| Wrong product | 10% | 5% | 5% | 10% | 5% | 15% |
| Excess inventory | 5% | 30% | 10% | 15% | 20% | 30% |
| Dissatisfaction | 10% | 15% | 5% | 10% | 5% | 15% |
| Expired product | 0% | 10% | 0% | 0% | 35% | 5% |
| Pricing dispute | 5% | 5% | 5% | 5% | 5% | 5% |

## 5.5 Return Quantity Logic

```python
def determine_return_quantity(
    original_quantity: int,
    reason: ReturnReason,
    rng: numpy.random.Generator,
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
```

## 5.6 Return Value Calculation

```python
def calculate_return_value(
    quantity_returned: int,
    unit_price: float,
    discount_pct: float,
    tax_rate: float,
) -> dict:
    """Calculate the financial impact of a return."""

    gross = quantity_returned * unit_price
    discount = gross * discount_pct / 100
    taxable = gross - discount
    tax = taxable * tax_rate / 100

    return_value = taxable + tax
    credit_note_amount = return_value  # Full credit for approved returns

    return {
        "return_value": round(return_value, 2),
        "credit_note_amount": round(credit_note_amount, 2),
    }
```

## 5.7 Return Timing

Returns occur between 1 and 60 days after the invoice date:

```python
def generate_return_date(
    invoice_date: date,
    reason: ReturnReason,
    rng: numpy.random.Generator,
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
```

## 5.8 Return Status Workflow

```
Return Created → "pending"
       │
  ┌────┴────┐
  │         │
Approved  Rejected  ← 90% approved, 10% rejected
  │         │
  ▼         ▼
"approved"  "rejected" (no credit)
  │
  ▼
"credited" ← Credit note issued
```

Status probabilities:
- Pending → Approved: 85%
- Pending → Rejected: 10%
- Pending (stuck): 5%
- Approved → Credited: 95% of approved

## 5.9 Return Number Format

```
RET-{YEAR}-{SEQUENCE:06d}
Credit notes: CN-{YEAR}-{SEQUENCE:06d}
```

## 5.10 Expected Output Volumes

| Scenario | Return Rate | Returns per 100K Sales |
|----------|-----------|----------------------|
| Low-discipline customer base | ~8% | 8,000 |
| Balanced customer base | ~5% | 5,000 |
| High-discipline customer base | ~2% | 2,000 |

For a balanced 100,000-sale dataset, expect approximately **4,000–6,000** return records.
