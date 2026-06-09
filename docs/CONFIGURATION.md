# CONFIGURATION

This document provides a comprehensive guide to configuring the Synthetic Commercial Data Generator.

---

## 1. Precedence Model

The generator resolves configuration variables according to the following strict hierarchy (highest priority overrides lowest):

1. **Command Line Arguments** (e.g. `--customers 100`)
2. **Environment Variables** (e.g. `CUSTOMER_COUNT=100`)
3. **YAML Config File** (e.g. `--config config.yaml`)
4. **Default Values**

---

## 2. Environment Variables reference

The following environment variables control dataset generation size, database credentials, and execution parameters:

| Environment Variable | Description | Defaults | Limits / Allowed Values |
|----------------------|-------------|----------|------------------------|
| `DATABASE_URL` | PostgreSQL connection string. Schema auto-converts standard `postgresql://` to async `postgresql+asyncpg://` | `postgresql+asyncpg://synth_user:secretpass@localhost:5432/synth_data` | Must be a valid PostgreSQL connection URI |
| `CUSTOMER_COUNT` | Total number of customers (profiles) to generate | `4000` | Minimum: `10`, Maximum: `100,000` |
| `SALES_COUNT` | Target number of raw sales records (invoice line items) | `150000` | Minimum: `100`, Maximum: `2,000,000` |
| `PAYMENT_COUNT` | Target number of raw payment records | `150000` | Minimum: `100`, Maximum: `2,000,000` |
| `RG_COUNT` | Target number of returned goods (RG) records | `35000` | Minimum: `10`, Maximum: `500,000` |
| `BATCH_SIZE` | Chunk size for SQLAlchemy database bulk inserts | `5000` | Minimum: `100`, Maximum: `50,000` |
| `SYNTH_SEED` | Seed for the numpy generator to ensure reproducibility | `42` | Must be a valid integer |
| `SYNTH_CONFIG_FILE` | Path to a YAML configuration file | `None` | Must be a valid local filepath |

---

## 3. Configuration via YAML File

You can store dataset target sizes in a YAML file (e.g., `config.yaml`):

```yaml
# config.yaml
customers: 4000
sales: 150000
payments: 150000
rgs: 35000
batch_size: 5000
seed: 42
```

To run the generator using this file:
```bash
python -m synth_data_creator.main --config config.yaml
```

---

## 4. Troubleshooting Schema Schemas

For async database operations, SQLAlchemy requires the `asyncpg` driver. If the user configures the URI with the standard `postgresql://` driver prefix, the service automatically converts it to `postgresql+asyncpg://` on startup to ensure a successful connection.
```text
Input:  postgresql://synth_user:pass@host:5432/db
Output: postgresql+asyncpg://synth_user:pass@host:5432/db
```
No manual driver specification in the connection string is required.
