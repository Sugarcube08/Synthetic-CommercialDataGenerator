import asyncio
import time
from datetime import date, timedelta
from typing import Any
import numpy as np
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.db.bulk_ops import bulk_insert
from synth_data_creator.db.schema_init import initialize_schema, verify_schema
from synth_data_creator.generation.customers.engine import generate_profiles
from synth_data_creator.generation.sales.engine import GlobalInvoiceTracker, generate_sales_for_customer, generate_order_dates
from synth_data_creator.generation.payments.engine import GlobalPaymentTracker, generate_payments_for_customer
from synth_data_creator.generation.returns.engine import GlobalReturnTracker, generate_returns_for_customer
from synth_data_creator.stats.kpi_calibration import calibrate_kpis
from synth_data_creator.stats.pareto import compute_gini

logger = structlog.get_logger()

# In-memory status store for tracking job states
jobs_status: dict[str, dict[str, Any]] = {}


async def db_writer_worker(queue: asyncio.Queue, engine: AsyncEngine, job_id: str) -> None:
    """Async background worker that consumes batches from the queue and inserts them into PostgreSQL."""
    while True:
        batch = await queue.get()
        if batch is None:
            queue.task_done()
            break

        table_name, records = batch
        try:
            if records:
                await bulk_insert(engine, table_name, records)
                # Update status count
                status = jobs_status.get(job_id)
                if status:
                    status_key = table_name.replace("raw_", "")
                    status["records"][status_key]["written"] += len(records)
        except Exception as e:
            logger.error("db_writer_worker_error", table=table_name, error=str(e))
            # Put error into job status
            status = jobs_status.get(job_id)
            if status:
                status["status"] = "failed"
                status["error"] = {
                    "code": "GENERATION_FAILED",
                    "message": f"Database bulk insert failed on table '{table_name}'",
                    "details": str(e)
                }
        finally:
            queue.task_done()


async def compute_db_kpis(engine: AsyncEngine, start_date: date, end_date: date) -> dict[str, Any]:
    """Execute optimized SQL queries to calculate current KPIs from the database."""
    total_days = (end_date - start_date).days or 1
    churn_limit = end_date - timedelta(days=180)

    queries = {
        "totals": text("""
            SELECT 
                COALESCE(SUM(invoice_amount), 0) as total_invoiced,
                COALESCE(SUM(balance_due), 0) as total_outstanding,
                COALESCE(SUM(amount_paid), 0) as total_paid_sales
            FROM raw_sales
        """),
        "payments": text("""
            SELECT COALESCE(SUM(payment_amount), 0) as total_payments
            FROM raw_payments
        """),
        "returns": text("""
            SELECT COALESCE(SUM(return_value), 0) as total_returns
            FROM raw_returns
        """),
        "delay": text("""
            SELECT COALESCE(AVG(p.payment_date - s.invoice_date), 0) as avg_delay
            FROM raw_payments p
            JOIN raw_sales s ON p.invoice_id = s.id
        """),
        "customer_rev": text("""
            SELECT customer_id, SUM(invoice_amount) as revenue
            FROM raw_sales
            GROUP BY customer_id
        """),
        "repeat": text("""
            SELECT 
                COUNT(DISTINCT customer_id) as repeat_custs,
                (SELECT COUNT(DISTINCT id) FROM customers) as total_custs
            FROM raw_sales
            GROUP BY customer_id
            HAVING COUNT(DISTINCT invoice_number) >= 2
        """),
        "churn": text(f"""
            SELECT COUNT(DISTINCT customer_id) as churned_custs
            FROM (
                SELECT customer_id, MAX(invoice_date) as max_date
                FROM raw_sales
                GROUP BY customer_id
            ) t
            WHERE max_date < '{churn_limit.isoformat()}'
        """)
    }

    async with engine.connect() as conn:
        # Totals
        res_totals = await conn.execute(queries["totals"])
        row_totals = res_totals.fetchone()
        total_invoiced = float(row_totals[0] if row_totals else 0.0)
        total_outstanding = float(row_totals[1] if row_totals else 0.0)

        # Payments
        res_payments = await conn.execute(queries["payments"])
        row_payments = res_payments.fetchone()
        total_payments = float(row_payments[0] if row_payments else 0.0)

        # Returns
        res_returns = await conn.execute(queries["returns"])
        row_returns = res_returns.fetchone()
        total_returns = float(row_returns[0] if row_returns else 0.0)

        # Delay
        res_delay = await conn.execute(queries["delay"])
        row_delay = res_delay.fetchone()
        avg_delay = float(row_delay[0] if row_delay else 0.0)

        # Customer Revenues
        res_revs = await conn.execute(queries["customer_rev"])
        revenues = [float(row[1]) for row in res_revs.fetchall()]

        # Repeat customers
        res_repeat = await conn.execute(queries["repeat"])
        repeat_rows = res_repeat.fetchall()
        repeat_count = len(repeat_rows)
        
        res_total_custs = await conn.execute(text("SELECT COUNT(*) FROM customers"))
        total_custs_row = res_total_custs.fetchone()
        total_custs = total_custs_row[0] if total_custs_row else 1
        if total_custs == 0:
            total_custs = 1

        # Churn
        res_churn = await conn.execute(queries["churn"])
        row_churn = res_churn.fetchone()
        churned_count = row_churn[0] if row_churn else 0

    # Calculate metrics
    dso = (total_outstanding / total_invoiced * total_days) if total_invoiced > 0 else 0.0
    collection_efficiency = (total_payments / total_invoiced) if total_invoiced > 0 else 0.0
    return_rate = (total_returns / total_invoiced) if total_invoiced > 0 else 0.0
    repeat_purchase_rate = repeat_count / total_custs
    churn_rate = churned_count / total_custs
    
    # Pareto Gini & top 20% revenue share
    gini = compute_gini(revenues)
    sorted_revs = sorted(revenues, reverse=True)
    top_20_count = max(1, int(len(sorted_revs) * 0.2))
    top_20_rev = sum(sorted_revs[:top_20_count])
    total_rev_sum = sum(sorted_revs)
    revenue_top20_pct = (top_20_rev / total_rev_sum) if total_rev_sum > 0 else 0.0

    return {
        "dso": round(dso, 2),
        "collection_efficiency": round(collection_efficiency, 4),
        "return_rate": round(return_rate, 4),
        "gini_coefficient": round(gini, 3),
        "revenue_top20_pct": round(revenue_top20_pct, 4),
        "repeat_purchase_rate": round(repeat_purchase_rate, 4),
        "churn_rate": round(churn_rate, 4),
        "avg_payment_delay_days": round(avg_delay, 1),
        "outstanding_ratio": round(total_outstanding / total_invoiced, 4) if total_invoiced > 0 else 0.0,
    }


async def run_generation_job(
    job_id: str,
    num_customers: int,
    start_date: date,
    end_date: date,
    seed: int | None,
    batch_size: int,
    engine: AsyncEngine,
    options: dict[str, Any],
) -> None:
    """Execute the full phased data generation pipeline asynchronously."""
    status = jobs_status[job_id]
    
    try:
        # Phase 1: Initialize Database Schema
        logger.info("job_phase_schema_init", job_id=job_id)
        status["phase"] = "schema"
        status["phase_progress"] = 0.10
        status["total_progress"] = 0.02
        
        await initialize_schema(engine, drop_existing=options.get("drop_existing", False))
        await verify_schema(engine)

        # Phase 2: Generate & Write Customers
        logger.info("job_phase_customers", job_id=job_id)
        status["phase"] = "customers"
        status["phase_progress"] = 0.0
        status["total_progress"] = 0.05

        # CPU bound customer profile generation run in executor
        profiles = await asyncio.to_thread(
            generate_profiles, num_customers, start_date, end_date, seed
        )
        
        status["records"]["customers"]["generated"] = len(profiles)
        
        # Format profiles for database insert
        customer_records = []
        for p in profiles:
            customer_records.append({
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
                    }
                }
            })
            
        await bulk_insert(engine, "customers", customer_records)
        status["records"]["customers"]["written"] = len(profiles)
        status["phase_progress"] = 1.0
        status["total_progress"] = 0.10

        # Phase 3, 4, 5: Sales, Payments, Returns
        logger.info("job_phase_transactions_start", job_id=job_id)
        status["phase"] = "generation"
        status["phase_progress"] = 0.0
        
        # Set up trackers and queues
        invoice_tracker = GlobalInvoiceTracker()
        payment_tracker = GlobalPaymentTracker()
        return_tracker = GlobalReturnTracker()
        
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=10)
        writer_task = asyncio.create_task(db_writer_worker(queue, engine, job_id))

        total_profiles = len(profiles)
        
        chunk_size = 1000
        for chunk_idx in range(0, total_profiles, chunk_size):
            # Check if job failed from worker side
            if status["status"] == "failed":
                break

            chunk_profiles = profiles[chunk_idx:chunk_idx + chunk_size]
            
            sales_chunk: list[dict[str, Any]] = []
            payments_chunk: list[dict[str, Any]] = []
            returns_chunk: list[dict[str, Any]] = []
            
            for profile in chunk_profiles:
                # Deterministic RNG per customer based on their profile seed
                rng = np.random.default_rng(profile.rng_seed)
                
                # 1. Sales
                sales_records = []
                if options.get("generate_sales", True):
                    order_dates = generate_order_dates(profile, start_date, end_date, rng)
                    sales_records = generate_sales_for_customer(profile, order_dates, invoice_tracker, rng)
                    
                # 2. Payments (modifies sales_records in place)
                payment_records = []
                if options.get("generate_payments", True) and sales_records:
                    payment_records = generate_payments_for_customer(profile, sales_records, payment_tracker, end_date, rng)
                    
                # 3. Returns
                return_records = []
                if options.get("generate_returns", True) and sales_records:
                    return_records = generate_returns_for_customer(profile, sales_records, return_tracker, end_date, rng)

                # Accumulate generated counts
                status["records"]["sales"]["generated"] += len(sales_records)
                status["records"]["payments"]["generated"] += len(payment_records)
                status["records"]["returns"]["generated"] += len(return_records)

                sales_chunk.extend(sales_records)
                payments_chunk.extend(payment_records)
                returns_chunk.extend(return_records)
                
            # Flush sales for this chunk
            if sales_chunk:
                for i in range(0, len(sales_chunk), batch_size):
                    await queue.put(("raw_sales", sales_chunk[i:i + batch_size]))
                
                # Wait for all sales of this chunk to be written
                await queue.join()
                
            # Check if job failed during sales insert
            if status["status"] == "failed":
                break

            # Flush payments for this chunk
            if payments_chunk:
                for i in range(0, len(payments_chunk), batch_size):
                    await queue.put(("raw_payments", payments_chunk[i:i + batch_size]))
                
            # Flush returns for this chunk
            if returns_chunk:
                for i in range(0, len(returns_chunk), batch_size):
                    await queue.put(("raw_returns", returns_chunk[i:i + batch_size]))
                
            # Wait for all payments and returns of this chunk to be written
            await queue.join()

            # Update progress
            processed = min(chunk_idx + chunk_size, total_profiles)
            status["phase_progress"] = processed / total_profiles
            # Scale total progress from 0.10 to 0.90
            status["total_progress"] = round(0.10 + 0.80 * (processed / total_profiles), 2)
            status["elapsed_seconds"] = round(time.time() - status["start_time"], 1)

        # Signal background worker to stop and wait for it
        await queue.put(None)
        await writer_task

        # Verify that background worker didn't set job status to failed
        if status["status"] == "failed":
            return

        # Phase 5: Post-Generation KPI Calibration
        if options.get("validate_kpis", True):
            logger.info("job_phase_kpi_validation", job_id=job_id)
            status["phase"] = "validation"
            status["phase_progress"] = 0.5
            
            kpis = await compute_db_kpis(engine, start_date, end_date)
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
            
            status["kpi_report"] = {
                "dso": kpis["dso"],
                "collection_efficiency": kpis["collection_efficiency"],
                "return_rate": kpis["return_rate"],
                "gini_coefficient": kpis["gini_coefficient"],
                "revenue_top20_pct": kpis["revenue_top20_pct"],
                "repeat_purchase_rate": kpis["repeat_purchase_rate"],
                "churn_rate": kpis["churn_rate"],
                "avg_payment_delay_days": kpis["avg_payment_delay_days"],
                "outstanding_ratio": kpis["outstanding_ratio"],
                "all_passed": calib["all_passed"],
                "details": calib["checks"],
            }
            
        status["status"] = "completed"
        status["phase"] = "complete"
        status["phase_progress"] = 1.0
        status["total_progress"] = 1.0
        status["elapsed_seconds"] = round(time.time() - status["start_time"], 1)
        logger.info("job_completed_successfully", job_id=job_id, elapsed=status["elapsed_seconds"])

    except Exception as e:
        logger.exception("job_failed_with_exception", job_id=job_id)
        status["status"] = "failed"
        status["error"] = {
            "code": "GENERATION_FAILED",
            "message": f"Error during generation: {str(e)}",
            "details": str(e)
        }
        status["elapsed_seconds"] = round(time.time() - status["start_time"], 1)
