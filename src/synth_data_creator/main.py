import argparse
import sys
import os
import uuid
import asyncio
from datetime import date, timedelta
import numpy as np
import yaml
from sqlalchemy import text

from synth_data_creator.db.engine import create_db_engine
from synth_data_creator.db.schema_init import initialize_schema
from synth_data_creator.db.bulk_ops import bulk_insert
from synth_data_creator.generation.customers.engine import generate_profiles
from synth_data_creator.generation.sales.engine import (
    GlobalInvoiceTracker,
    generate_sales_for_customer,
    generate_order_dates,
)
from synth_data_creator.generation.payments.engine import (
    GlobalPaymentTracker,
    generate_payments_for_customer,
)
from synth_data_creator.generation.returns.engine import (
    GlobalReturnTracker,
    generate_returns_for_customer,
)


async def batch_insert_all(engine, table_name, records, batch_size):
    for i in range(0, len(records), batch_size):
        chunk = records[i : i + batch_size]
        await bulk_insert(engine, table_name, chunk)


async def async_main() -> None:
    try:
        # 1. Load configuration with correct precedence:
        # CLI Args > Env Vars > Config File > Defaults
        default_config = {
            "customers": 4000,
            "sales": 150000,
            "payments": 150000,
            "rgs": 35000,
            "batch_size": 5000,
            "database_url": "postgresql+asyncpg://synth_user:secretpass@localhost:5432/synth_data",
            "seed": 42,
        }

        parser = argparse.ArgumentParser(description="Synthetic Commercial Data Generator (Batch)")
        parser.add_argument("-c", "--customers", type=int, help="Number of customers to generate")
        parser.add_argument("-s", "--sales", type=int, help="Target sales records to generate")
        parser.add_argument("-p", "--payments", type=int, help="Target payment records to generate")
        parser.add_argument("-r", "--rgs", type=int, help="Target return (RG) records to generate")
        parser.add_argument("-b", "--batch-size", type=int, help="Batch size for database insert")
        parser.add_argument("-d", "--database-url", type=str, help="PostgreSQL connection URI")
        parser.add_argument("--seed", type=int, help="Random seed for generation")
        parser.add_argument("--config", type=str, help="Path to config file (YAML)")

        args, unknown = parser.parse_known_args()

        # Load configuration file if specified
        config_file_path = args.config or os.environ.get("SYNTH_CONFIG_FILE")
        file_config = {}
        if config_file_path and os.path.exists(config_file_path):
            with open(config_file_path, "r") as f:
                file_config = yaml.safe_load(f) or {}

        def get_val(arg_name, env_name, config_key, default_val):
            val = getattr(args, arg_name, None)
            if val is not None:
                return val
            val = os.environ.get(env_name)
            if val is not None:
                if isinstance(default_val, int):
                    try:
                        return int(val)
                    except ValueError:
                        pass
                return val
            val = file_config.get(config_key)
            if val is not None:
                return val
            return default_val

        target_customers = get_val(
            "customers", "CUSTOMER_COUNT", "customers", default_config["customers"]
        )
        target_sales = get_val("sales", "SALES_COUNT", "sales", default_config["sales"])
        target_payments = get_val(
            "payments", "PAYMENT_COUNT", "payments", default_config["payments"]
        )
        target_rgs = get_val("rgs", "RG_COUNT", "rgs", default_config["rgs"])
        batch_size = get_val("batch_size", "BATCH_SIZE", "batch_size", default_config["batch_size"])
        db_url = get_val(
            "database_url", "DATABASE_URL", "database_url", default_config["database_url"]
        )
        seed = get_val("seed", "SYNTH_SEED", "seed", default_config["seed"])

        if seed is not None:
            try:
                seed = int(seed)
            except (ValueError, TypeError):
                seed = 42
        else:
            seed = 42

        # Convert postgresql:// scheme to postgresql+asyncpg:// if needed for async pg driver
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # 2. Connect to PostgreSQL and initialize schema
        engine = create_db_engine(db_url)
        await initialize_schema(engine, drop_existing=True)

        start_date = date.today() - timedelta(days=24 * 30)  # Default 24 months
        end_date = date.today()

        # 3. Generate Customers
        print("Generating Customers...", flush=True)
        profiles = generate_profiles(target_customers, start_date, end_date, seed)
        customer_records = []
        for p in profiles:
            customer_records.append(
                {
                    "id": p.id,
                    "customer_code": p.customer_code,
                    "business_name": p.business_name,
                    "contact_name": p.contact_name,
                    "email": p.email,
                    "phone": p.phone,
                    "address_line1": p.address_line1,
                    "address_line2": "",
                    "city": p.city,
                    "state": p.state,
                    "postal_code": p.postal_code,
                    "country": p.country,
                    "business_type": p.business_type,
                    "registration_date": p.registration_date,
                    "credit_limit": p.credit_limit,
                    "payment_terms_days": p.payment_terms_days,
                    "is_active": True,
                    "behavioral_profile": {
                        "volume_segment": p.volume_segment.value,
                        "frequency_segment": p.frequency_segment.value,
                        "payment_segment": p.payment_segment.value,
                        "outstanding_segment": p.outstanding_segment.value,
                        "discipline_segment": p.discipline_segment.value,
                        "lifecycle_segment": p.lifecycle_segment.value,
                        "params": {
                            "avg_order_value": p.avg_order_value,
                            "order_frequency_days": p.order_frequency_days,
                            "payment_delay_mean": p.payment_delay_mean,
                            "payment_delay_std": p.payment_delay_std,
                            "return_probability": p.return_probability,
                            "growth_rate": p.growth_rate_monthly,
                        },
                    },
                }
            )
        print(f"Generated {len(customer_records):,} Customers", flush=True)
        print("", flush=True)

        # 4. Generate Sales
        print("Generating Sales...", flush=True)
        invoice_tracker = GlobalInvoiceTracker()
        sales_records = []
        profile_cycle = 0

        while len(sales_records) < target_sales:
            cycle_rng_offset = profile_cycle * 12345
            for p in profiles:
                if len(sales_records) >= target_sales:
                    break

                rng = np.random.default_rng(p.rng_seed + cycle_rng_offset + seed)
                s_date = start_date - timedelta(days=365 * profile_cycle)
                e_date = end_date - timedelta(days=365 * profile_cycle)

                order_dates = generate_order_dates(p, s_date, e_date, rng)
                cust_sales = generate_sales_for_customer(p, order_dates, invoice_tracker, rng)

                for sale in cust_sales:
                    if len(sales_records) >= target_sales:
                        break
                    sales_records.append(sale)
            profile_cycle += 1
            if profile_cycle > 100 and len(sales_records) == 0:
                raise RuntimeError("Failed to generate any sales records. Check configuration.")
        print(f"Generated {len(sales_records):,} Sales", flush=True)
        print("", flush=True)

        # Group sales by customer ID for payment/return generator compatibility
        sales_by_customer = {}
        for sale in sales_records:
            cid = sale["customer_id"]
            if cid not in sales_by_customer:
                sales_by_customer[cid] = []
            sales_by_customer[cid].append(sale)

        # 5. Generate Payments
        print("Generating Payments...", flush=True)
        payment_tracker = GlobalPaymentTracker()
        payment_records = []
        profile_cycle = 0

        while len(payment_records) < target_payments:
            cycle_rng_offset = profile_cycle * 54321
            for p in profiles:
                if len(payment_records) >= target_payments:
                    break

                cust_sales = sales_by_customer.get(p.id, [])
                if not cust_sales:
                    continue

                rng = np.random.default_rng(p.rng_seed + cycle_rng_offset + seed)
                cust_payments = generate_payments_for_customer(
                    p, cust_sales, payment_tracker, end_date, rng
                )

                for pay in cust_payments:
                    if len(payment_records) >= target_payments:
                        break
                    pay["id"] = uuid.uuid4()
                    if "sale_invoice_number" in pay:
                        del pay["sale_invoice_number"]
                    payment_records.append(pay)
            profile_cycle += 1
            if profile_cycle > 100 and len(payment_records) == 0:
                raise RuntimeError("Failed to generate any payment records. Check configuration.")
        print(f"Generated {len(payment_records):,} Payments", flush=True)
        print("", flush=True)

        # 6. Generate RG Records
        print("Generating RG Records...", flush=True)
        return_tracker = GlobalReturnTracker()
        return_records = []
        profile_cycle = 0

        while len(return_records) < target_rgs:
            cycle_rng_offset = profile_cycle * 99999
            for p in profiles:
                if len(return_records) >= target_rgs:
                    break

                cust_sales = sales_by_customer.get(p.id, [])
                if not cust_sales:
                    continue

                rng = np.random.default_rng(p.rng_seed + cycle_rng_offset + seed)
                cust_returns = generate_returns_for_customer(
                    p, cust_sales, return_tracker, end_date, rng
                )

                for ret in cust_returns:
                    if len(return_records) >= target_rgs:
                        break
                    ret["id"] = uuid.uuid4()
                    if "sale_invoice_number" in ret:
                        del ret["sale_invoice_number"]
                    return_records.append(ret)
            profile_cycle += 1
            if profile_cycle > 100 and len(return_records) == 0:
                raise RuntimeError(
                    "Failed to generate any returns (RG) records. Check configuration."
                )
        print(f"Generated {len(return_records):,} RG Records", flush=True)
        print("", flush=True)

        # 7. Validate Relationships (re-calculate paid amounts/balances to match actual payments)
        # Reset sales fields
        for s in sales_records:
            s["amount_paid"] = 0.0
            s["balance_due"] = float(s["invoice_amount"])
            s["payment_status"] = "unpaid"

        payments_by_sale = {}
        for p in payment_records:
            sid = p["invoice_id"]
            if sid not in payments_by_sale:
                payments_by_sale[sid] = []
            payments_by_sale[sid].append(p)

        for s in sales_records:
            sid = s["id"]
            pays = payments_by_sale.get(sid, [])
            total_paid = sum(float(p["payment_amount"]) for p in pays)
            total_paid = round(total_paid, 2)

            invoice_amount = float(s["invoice_amount"])
            due_date = s["due_date"]

            if total_paid >= invoice_amount:
                status = "paid"
                balance = 0.0
            elif total_paid > 0:
                status = "partial"
                balance = round(invoice_amount - total_paid, 2)
            else:
                status = "overdue" if end_date > due_date else "unpaid"
                balance = invoice_amount

            s["amount_paid"] = total_paid
            s["balance_due"] = balance
            s["payment_status"] = status

        # 8. Populate Database (Bulk Insert in Batches)
        print("Populating Database...", flush=True)
        await batch_insert_all(engine, "customers", customer_records, batch_size)
        await batch_insert_all(engine, "raw_sales", sales_records, batch_size)
        await batch_insert_all(engine, "raw_payments", payment_records, batch_size)
        await batch_insert_all(engine, "raw_returns", return_records, batch_size)
        print("Completed", flush=True)
        print("", flush=True)

        # 9. Verification
        print("Verification:", flush=True)
        async with engine.connect() as conn:
            res_cust = await conn.execute(text("SELECT COUNT(*) FROM customers"))
            actual_customers = res_cust.scalar()

            res_sales = await conn.execute(text("SELECT COUNT(*) FROM raw_sales"))
            actual_sales = res_sales.scalar()

            res_payments = await conn.execute(text("SELECT COUNT(*) FROM raw_payments"))
            actual_payments = res_payments.scalar()

            res_returns = await conn.execute(text("SELECT COUNT(*) FROM raw_returns"))
            actual_returns = res_returns.scalar()

        print(f"Customers: {actual_customers}", flush=True)
        print(f"Sales: {actual_sales}", flush=True)
        print(f"Payments: {actual_payments}", flush=True)
        print(f"RG: {actual_returns}", flush=True)
        print("", flush=True)

        await engine.dispose()

        # Check if actual counts match requested targets
        if (
            actual_customers == target_customers
            and actual_sales == target_sales
            and actual_payments == target_payments
            and actual_returns == target_rgs
        ):
            print("Synthetic Dataset Generation Complete", flush=True)
            sys.exit(0)
        else:
            print("Verification failed: actual counts do not match target counts.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
