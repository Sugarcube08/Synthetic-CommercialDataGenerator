import argparse
import sys
import os
import asyncio
from datetime import date, timedelta
import structlog

from synth_data_creator.db.engine import create_db_engine
from synth_data_creator.db.schema_init import initialize_schema, verify_schema
from synth_data_creator.generation.simulation import simulate_ecosystem
from synth_data_creator.generation.exporters import export_all_modes
from synth_data_creator.generation.orchestrator import compute_db_kpis
from synth_data_creator.stats.kpi_calibration import calibrate_kpis

logger = structlog.get_logger()


async def async_main() -> None:
    try:
        # 1. Load configuration with correct precedence: CLI Args > Env Vars > Defaults
        default_config = {
            "customers": 4000,
            "sales": 150000,
            "payments": 150000,
            "rgs": 35000,
            "batch_size": 5000,
            "database_url": "postgresql+asyncpg://synth_user:secretpass@localhost:5432/synth_data",
            "seed": 42,
            "months": 120,
            "duplication_rate": 0.05,
            "export_dir": "exports",
        }

        parser = argparse.ArgumentParser(description="Synthetic Commercial B2B Telemetry Simulator")
        parser.add_argument("-c", "--customers", type=int, help="Number of customers to generate")
        parser.add_argument("-s", "--sales", type=int, help="Target sales records to generate")
        parser.add_argument("-p", "--payments", type=int, help="Target payment records to generate")
        parser.add_argument("-r", "--rgs", type=int, help="Target return (RG) records to generate")
        parser.add_argument("-b", "--batch-size", type=int, help="Batch size for database insert")
        parser.add_argument("-d", "--database-url", type=str, help="PostgreSQL connection URI")
        parser.add_argument("-m", "--months", type=int, help="Months of history to generate")
        parser.add_argument("--seed", type=int, help="Random seed for generation")
        parser.add_argument("--duplication-rate", type=float, help="Spelling duplication percentage for dirty data")
        parser.add_argument("--export-dir", type=str, help="Directory to export CSV outputs")

        args, unknown = parser.parse_known_args()

        def get_val(arg_name, env_name, default_val):
            val = getattr(args, arg_name, None)
            if val is not None:
                return val
            val = os.environ.get(env_name)
            if val is not None:
                if isinstance(default_val, int):
                    return int(val)
                elif isinstance(default_val, float):
                    return float(val)
                return val
            return default_val

        target_customers = get_val("customers", "CUSTOMER_COUNT", default_config["customers"])
        target_sales = get_val("sales", "SALES_COUNT", default_config["sales"])
        target_payments = get_val("payments", "PAYMENT_COUNT", default_config["payments"])
        target_rgs = get_val("rgs", "RG_COUNT", default_config["rgs"])
        batch_size = get_val("batch_size", "BATCH_SIZE", default_config["batch_size"])
        db_url = get_val("database_url", "DATABASE_URL", default_config["database_url"])
        seed = get_val("seed", "SYNTH_SEED", default_config["seed"])
        target_months = get_val("months", "DATE_RANGE_MONTHS", default_config["months"])
        duplication_rate = get_val("duplication_rate", "DUPLICATION_RATE", default_config["duplication_rate"])
        export_dir = get_val("export_dir", "EXPORT_DIR", default_config["export_dir"])

        # Convert schemes to async
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # 2. Connect to database and drop/re-init schema
        print("Initializing database connection...", flush=True)
        engine = create_db_engine(db_url)
        await initialize_schema(engine, drop_existing=True)
        await verify_schema(engine)

        start_date = date.today() - timedelta(days=target_months * 30)
        end_date = date.today()

        # 3. Execute Chronological Simulation Loop
        print("Starting Behavioral Commercial Telemetry Simulation...", flush=True)
        sim_results = await simulate_ecosystem(
            engine=engine,
            num_customers=target_customers,
            start_date=start_date,
            end_date=end_date,
            seed=seed,
            target_sales=target_sales,
            target_payments=target_payments,
            target_rgs=target_rgs,
            batch_size=batch_size
        )

        print(f"Generated {len(sim_results['customers']):,} Customers", flush=True)
        print(f"Generated {len(sim_results['raw_sales']):,} Invoices", flush=True)
        print(f"Generated {len(sim_results['raw_payments']):,} Payments", flush=True)
        print(f"Generated {len(sim_results['raw_returns']):,} Returns", flush=True)
        print("", flush=True)

        # 4. Export Outputs in Modes (Mode 1 to Mode 5)
        print(f"Exporting Mode 1-5 outputs to '{export_dir}'...", flush=True)
        export_all_modes(sim_results, export_dir, duplication_rate, seed)
        print("Export Completed.", flush=True)
        print("", flush=True)

        # 5. Verification & KPI Calibration
        print("Running Post-Generation KPI Calibration...", flush=True)
        kpis = await compute_db_kpis(engine, start_date, end_date)
        print(f"Calculated KPIs: {kpis}", flush=True)

        calib = calibrate_kpis(
            dso=kpis["dso"],
            collection_efficiency=kpis["collection_efficiency"],
            return_rate=kpis["return_rate"],
            gini_coefficient=kpis["gini_coefficient"],
            revenue_top20_pct=kpis["revenue_top20_pct"],
            repeat_purchase_rate=kpis["repeat_purchase_rate"],
            churn_rate=kpis["churn_rate"],
            avg_payment_delay_days=kpis["avg_payment_delay_days"],
            outstanding_ratio=kpis["outstanding_ratio"],
        )

        print(f"KPI checks report: {calib['checks']}", flush=True)

        await engine.dispose()

        if calib["all_passed"]:
            print("Synthetic Dataset Generation Complete (Pass)", flush=True)
            sys.exit(0)
        else:
            print("Verification failed: calculated KPIs fall outside configured industry tolerances.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Simulation execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
