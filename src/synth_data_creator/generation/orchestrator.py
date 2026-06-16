import asyncio
import time
import os
from datetime import date, timedelta
from typing import Any
import numpy as np
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.db.bulk_ops import bulk_insert
from synth_data_creator.db.schema_init import initialize_schema, verify_schema
from synth_data_creator.generation.simulation import simulate_ecosystem
from synth_data_creator.generation.exporters import export_all_modes
from synth_data_creator.stats.kpi_calibration import calibrate_kpis
from synth_data_creator.stats.pareto import compute_gini

logger = structlog.get_logger()

# In-memory status store for tracking job states
jobs_status: dict[str, dict[str, Any]] = {}


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
        
        await initialize_schema(engine, drop_existing=options.get("drop_existing", True))
        await verify_schema(engine)

        # Phase 2: Run Behavioral Simulation
        logger.info("job_phase_simulation", job_id=job_id)
        status["phase"] = "generation"
        status["phase_progress"] = 0.50
        status["total_progress"] = 0.40

        run_seed = seed if seed is not None else 42
        
        # Chronological day-by-day B2B simulation
        sim_results = await simulate_ecosystem(
            engine=engine,
            num_customers=num_customers,
            start_date=start_date,
            end_date=end_date,
            seed=run_seed,
            target_sales=options.get("sales_count", 150000),
            target_payments=options.get("payment_count", 150000),
            target_rgs=options.get("rg_count", 35000),
            batch_size=batch_size
        )
        
        # Populate counts
        status["records"]["customers"]["generated"] = len(sim_results["customers"])
        status["records"]["customers"]["written"] = len(sim_results["customers"])
        status["records"]["sales"] = {"generated": len(sim_results["raw_sales"]), "written": len(sim_results["raw_sales"])}
        status["records"]["payments"] = {"generated": len(sim_results["raw_payments"]), "written": len(sim_results["raw_payments"])}
        status["records"]["returns"] = {"generated": len(sim_results["raw_returns"]), "written": len(sim_results["raw_returns"])}

        # Phase 3: Export Datasets
        logger.info("job_phase_exporters", job_id=job_id)
        status["phase"] = "exporting"
        status["phase_progress"] = 0.80
        status["total_progress"] = 0.80
        
        export_dir = os.path.join("exports", job_id)
        export_all_modes(
            data=sim_results,
            output_dir=export_dir,
            duplication_rate=options.get("duplication_rate", 0.05),
            seed=run_seed
        )

        # Phase 4: Post-Generation KPI Calibration
        if options.get("validate_kpis", True):
            logger.info("job_phase_kpi_validation", job_id=job_id)
            status["phase"] = "validation"
            status["phase_progress"] = 0.90
            
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
            
            # Fail if validation check fails (V2 Validation Requirement)
            if not calib["all_passed"]:
                raise ValueError(f"KPI Calibration failed: {calib['checks']}")
            
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
        raise
