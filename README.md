# Synthetic Commercial Data Generator (Batch)

The synthetic data generator is a Docker-executed batch service that generates configurable synthetic business datasets and populates PostgreSQL before terminating.

---

## 1. Purpose

This tool is designed to generate statistically realistic, behaviorally consistent B2B commercial dataset records (Customers, Invoice/Sales, Payments, and Returned Goods) directly inside a PostgreSQL database. It is intended for:
- Development and testing database initialization.
- Analytics and dashboard testing.
- Benchmarking query performance with target scale datasets.

It runs as a one-time batch job, initializes the database schema, bulk-inserts generated records in configured chunk sizes, validates the inserted counts against targets, and terminates cleanly.

---

## 2. Setup

### Prerequisites
- Docker and Docker Compose
- Python ≥ 3.12 (if running locally without Docker)
- `uv` package manager (optional, recommended for local development)

### Initial Configuration
Copy the env template file to `.env`:
```bash
cp .env.example .env
```
Edit the `.env` file to customize your database URI and default dataset target parameters.

---

## 3. Environment Variables

The batch service reads configuration from the environment with the following variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string (supports standard or async pg schemes) | `postgresql://synth_user:secretpass@host.docker.internal:5432/ir_econiq` |
| `CUSTOMER_COUNT` | Number of customer profiles to generate | `4000` |
| `SALES_COUNT` | Target number of sales (invoice line items) to generate | `150000` |
| `PAYMENT_COUNT` | Target number of payments to generate | `150000` |
| `RG_COUNT` | Target number of returned goods (RG) records to generate | `35000` |
| `BATCH_SIZE` | Chunk size for SQLAlchemy database bulk inserts | `5000` |
| `SYNTH_SEED` | Seed for deterministic/reproducible random generation | `42` |

---

## 4. Docker Usage

### Build the Image
To build the generator container:
```bash
docker compose build
```

### Run the Generator
To execute the one-time batch population:
```bash
docker compose up synth-generator
```

Upon completion, the container will print the generated dataset counts, verify the database records, and automatically exit with code `0`.

---

## 5. Example Override Commands

You can run the batch generator with customized target sizes on-the-fly without changing the `.env` file:

```bash
# Generate a small test dataset
CUSTOMER_COUNT=10 SALES_COUNT=100 PAYMENT_COUNT=100 RG_COUNT=20 docker compose up synth-generator
```

```bash
# Run with a custom database URL and different seed
DATABASE_URL="postgresql://user:pass@host.docker.internal:5432/other_db" SYNTH_SEED=100 docker compose up synth-generator
```

---

## 6. Expected Output

A successful run logs progress and verification output to stdout:

```text
Starting Synthetic Dataset Generation...
Target Customers: 4000
Target Sales: 150000
Target Payments: 150000
Target RGs: 35000

Generating Customers...
Generated 4,000 Customers

Generating Sales...
Generated 150,000 Sales

Generating Payments...
Generated 150,000 Payments

Generating RG Records...
Generated 35,000 RG Records

Populating Database...
Completed

Verification:
Customers: 4000
Sales: 150000
Payments: 150000
RG: 35000

Synthetic Dataset Generation Complete
```

---

## 7. Verification Steps

To manually double-check that the PostgreSQL database has been correctly populated, run the following SQL queries inside your database client:

```sql
-- Count customers
SELECT COUNT(*) FROM customers; -- Should match CUSTOMER_COUNT

-- Count sales records
SELECT COUNT(*) FROM raw_sales; -- Should match SALES_COUNT

-- Count payments
SELECT COUNT(*) FROM raw_payments; -- Should match PAYMENT_COUNT

-- Count returned goods
SELECT COUNT(*) FROM raw_returns; -- Should match RG_COUNT
```
