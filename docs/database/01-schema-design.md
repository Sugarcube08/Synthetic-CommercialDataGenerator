# 01 — Database Schema Design

## 1.1 Schema Overview

The microservice operates on 4 core tables within a single PostgreSQL schema (default: `public`). All tables use UUID primary keys for distributed-friendly identity and avoid sequential IDs that leak business information.

```
┌──────────────┐
│  customers   │
│──────────────│
│ PK: id (UUID)│
└──────┬───────┘
       │ 1:N
       ├───────────────────────┐
       │                       │
┌──────┴───────┐         ┌────┴──────────┐
│  raw_sales   │         │  raw_returns  │
│──────────────│         │───────────────│
│ PK: id       │◄────────│ FK: sale_id   │
│ FK: cust_id  │         │ FK: cust_id   │
└──────┬───────┘         └───────────────┘
       │ 1:N
┌──────┴───────────┐
│  raw_payments    │
│──────────────────│
│ PK: id           │
│ FK: invoice_id   │
│ FK: cust_id      │
└──────────────────┘
```

## 1.2 Table: `customers`

Stores customer master data and the serialized behavioral profile.

```sql
CREATE TABLE IF NOT EXISTS customers (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_code   VARCHAR(20) NOT NULL UNIQUE,
    business_name   VARCHAR(200) NOT NULL,
    contact_name    VARCHAR(150),
    email           VARCHAR(254),
    phone           VARCHAR(20),
    address_line1   VARCHAR(300),
    address_line2   VARCHAR(300),
    city            VARCHAR(100),
    state           VARCHAR(100),
    postal_code     VARCHAR(20),
    country         VARCHAR(3)  NOT NULL DEFAULT 'IND',

    -- Business metadata
    business_type       VARCHAR(50),    -- 'retailer', 'distributor', 'manufacturer'
    registration_date   DATE NOT NULL,
    credit_limit        NUMERIC(15, 2) NOT NULL DEFAULT 0,
    payment_terms_days  INTEGER NOT NULL DEFAULT 30,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    -- Behavioral profile (JSON for flexibility)
    behavioral_profile  JSONB NOT NULL,

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_customers_code ON customers(customer_code);
CREATE INDEX IF NOT EXISTS idx_customers_active ON customers(is_active);
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers(city);
CREATE INDEX IF NOT EXISTS idx_customers_reg_date ON customers(registration_date);
CREATE INDEX IF NOT EXISTS idx_customers_profile ON customers USING GIN(behavioral_profile);
```

### Column Details

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | No | Primary key |
| `customer_code` | VARCHAR(20) | No | Human-readable identifier (e.g., `CUST-00001`) |
| `business_name` | VARCHAR(200) | No | Legal business name |
| `contact_name` | VARCHAR(150) | Yes | Primary contact person |
| `email` | VARCHAR(254) | Yes | Contact email |
| `phone` | VARCHAR(20) | Yes | Contact phone |
| `address_line1` | VARCHAR(300) | Yes | Street address |
| `city` | VARCHAR(100) | Yes | City |
| `state` | VARCHAR(100) | Yes | State/Province |
| `postal_code` | VARCHAR(20) | Yes | ZIP/Postal code |
| `country` | VARCHAR(3) | No | ISO 3166-1 alpha-3 country code |
| `business_type` | VARCHAR(50) | Yes | Customer business classification |
| `registration_date` | DATE | No | Date customer was onboarded |
| `credit_limit` | NUMERIC(15,2) | No | Maximum credit allowance |
| `payment_terms_days` | INTEGER | No | Standard payment terms in days |
| `is_active` | BOOLEAN | No | Whether customer is currently active |
| `behavioral_profile` | JSONB | No | Serialized behavioral segment assignments |

### Behavioral Profile JSONB Structure

```json
{
  "volume_segment": "whale",
  "frequency_segment": "frequent",
  "payment_segment": "fast_payer",
  "outstanding_segment": "fast_clearer",
  "discipline_segment": "disciplined",
  "lifecycle_segment": "growing",
  "params": {
    "avg_order_value": 85000.00,
    "order_frequency_days": 7,
    "payment_delay_mean": 3,
    "payment_delay_std": 1.5,
    "return_probability": 0.02,
    "growth_rate": 0.03
  }
}
```

---

## 1.3 Table: `raw_sales`

Stores individual sales/invoice records.

```sql
CREATE TABLE IF NOT EXISTS raw_sales (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID        NOT NULL REFERENCES customers(id),
    invoice_number      VARCHAR(30) NOT NULL UNIQUE,
    order_date          DATE        NOT NULL,
    invoice_date        DATE        NOT NULL,
    due_date            DATE        NOT NULL,

    -- Product details
    product_category    VARCHAR(100) NOT NULL,
    product_name        VARCHAR(200) NOT NULL,
    quantity            INTEGER      NOT NULL CHECK (quantity > 0),
    unit_price          NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),

    -- Financial calculations
    gross_amount        NUMERIC(15, 2) NOT NULL,   -- quantity * unit_price
    discount_pct        NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (discount_pct >= 0 AND discount_pct <= 100),
    discount_amount     NUMERIC(15, 2) NOT NULL DEFAULT 0,
    taxable_amount      NUMERIC(15, 2) NOT NULL,   -- gross - discount
    tax_rate            NUMERIC(5, 2) NOT NULL DEFAULT 18.00,
    cgst_amount         NUMERIC(15, 2) NOT NULL DEFAULT 0,
    sgst_amount         NUMERIC(15, 2) NOT NULL DEFAULT 0,
    igst_amount         NUMERIC(15, 2) NOT NULL DEFAULT 0,
    total_tax           NUMERIC(15, 2) NOT NULL,
    invoice_amount      NUMERIC(15, 2) NOT NULL,   -- taxable + tax

    -- Payment tracking
    payment_terms_days  INTEGER NOT NULL DEFAULT 30,
    amount_paid         NUMERIC(15, 2) NOT NULL DEFAULT 0,
    balance_due         NUMERIC(15, 2) NOT NULL,
    payment_status      VARCHAR(20) NOT NULL DEFAULT 'unpaid'
                        CHECK (payment_status IN ('unpaid', 'partial', 'paid', 'overdue')),

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sales_customer ON raw_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_invoice_num ON raw_sales(invoice_number);
CREATE INDEX IF NOT EXISTS idx_sales_order_date ON raw_sales(order_date);
CREATE INDEX IF NOT EXISTS idx_sales_due_date ON raw_sales(due_date);
CREATE INDEX IF NOT EXISTS idx_sales_status ON raw_sales(payment_status);
CREATE INDEX IF NOT EXISTS idx_sales_category ON raw_sales(product_category);
```

### Column Details

| Column | Type | Description |
|--------|------|-------------|
| `invoice_number` | VARCHAR(30) | Unique invoice ID (e.g., `INV-2024-000001`) |
| `order_date` | DATE | When the customer placed the order |
| `invoice_date` | DATE | When the invoice was generated (≥ order_date) |
| `due_date` | DATE | invoice_date + payment_terms_days |
| `product_category` | VARCHAR(100) | Product category (e.g., "Electronics", "FMCG") |
| `product_name` | VARCHAR(200) | Specific product within category |
| `gross_amount` | NUMERIC | quantity × unit_price |
| `discount_pct` | NUMERIC | Percentage discount applied |
| `discount_amount` | NUMERIC | gross_amount × discount_pct / 100 |
| `taxable_amount` | NUMERIC | gross_amount − discount_amount |
| `tax_rate` | NUMERIC | Applicable GST rate |
| `cgst_amount` | NUMERIC | Central GST (intra-state) |
| `sgst_amount` | NUMERIC | State GST (intra-state) |
| `igst_amount` | NUMERIC | Integrated GST (inter-state) |
| `total_tax` | NUMERIC | cgst + sgst OR igst |
| `invoice_amount` | NUMERIC | taxable_amount + total_tax |
| `amount_paid` | NUMERIC | Running total of payments received |
| `balance_due` | NUMERIC | invoice_amount − amount_paid |
| `payment_status` | VARCHAR | Derived status: unpaid/partial/paid/overdue |

---

## 1.4 Table: `raw_payments`

Records individual payment transactions against invoices.

```sql
CREATE TABLE IF NOT EXISTS raw_payments (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID        NOT NULL REFERENCES customers(id),
    invoice_id      UUID        NOT NULL REFERENCES raw_sales(id),
    payment_number  VARCHAR(30) NOT NULL UNIQUE,
    payment_date    DATE        NOT NULL,
    payment_amount  NUMERIC(15, 2) NOT NULL CHECK (payment_amount > 0),
    payment_mode    VARCHAR(30) NOT NULL DEFAULT 'bank_transfer'
                    CHECK (payment_mode IN (
                        'bank_transfer', 'cheque', 'cash',
                        'upi', 'neft', 'rtgs', 'credit_note'
                    )),
    reference_number VARCHAR(50),
    remarks         VARCHAR(500),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_payments_customer ON raw_payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON raw_payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_date ON raw_payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_mode ON raw_payments(payment_mode);
```

### Design Notes

- Multiple payments per invoice are supported (partial payment scenario)
- `payment_amount` is always positive; negative adjustments use credit notes
- `payment_mode` reflects common Indian B2B payment methods
- `reference_number` stores UTR/cheque number/UPI reference

---

## 1.5 Table: `raw_returns`

Records product return events linked to original sales.

```sql
CREATE TABLE IF NOT EXISTS raw_returns (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID        NOT NULL REFERENCES customers(id),
    sale_id         UUID        NOT NULL REFERENCES raw_sales(id),
    return_number   VARCHAR(30) NOT NULL UNIQUE,
    return_date     DATE        NOT NULL,
    return_reason   VARCHAR(50) NOT NULL
                    CHECK (return_reason IN (
                        'damaged_goods', 'delivery_issues',
                        'quality_defect', 'wrong_product',
                        'excess_inventory', 'customer_dissatisfaction',
                        'expired_product', 'pricing_dispute'
                    )),
    quantity_returned   INTEGER      NOT NULL CHECK (quantity_returned > 0),
    return_value        NUMERIC(15, 2) NOT NULL CHECK (return_value >= 0),
    credit_note_number  VARCHAR(30),
    credit_note_amount  NUMERIC(15, 2) DEFAULT 0,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'credited')),
    remarks             VARCHAR(500),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_returns_customer ON raw_returns(customer_id);
CREATE INDEX IF NOT EXISTS idx_returns_sale ON raw_returns(sale_id);
CREATE INDEX IF NOT EXISTS idx_returns_date ON raw_returns(return_date);
CREATE INDEX IF NOT EXISTS idx_returns_reason ON raw_returns(return_reason);
CREATE INDEX IF NOT EXISTS idx_returns_status ON raw_returns(status);
```

---

## 1.6 Referential Integrity Map

```
customers.id ──┬──▶ raw_sales.customer_id
               ├──▶ raw_payments.customer_id
               └──▶ raw_returns.customer_id

raw_sales.id  ──┬──▶ raw_payments.invoice_id
               └──▶ raw_returns.sale_id
```

**Cascade Rules:**
- `ON DELETE RESTRICT` — prevent customer deletion while transactions exist
- No cascading deletes to preserve audit trail integrity

## 1.7 Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Tables | snake_case, plural | `raw_sales` |
| Columns | snake_case | `payment_terms_days` |
| Primary keys | `id` | `id UUID` |
| Foreign keys | `{referenced_table_singular}_id` | `customer_id` |
| Indexes | `idx_{table}_{column}` | `idx_sales_customer` |
| Check constraints | Inline | `CHECK (quantity > 0)` |
