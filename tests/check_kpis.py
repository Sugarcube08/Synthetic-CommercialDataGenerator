import asyncio
from datetime import date, timedelta
from synth_data_creator.db.engine import create_db_engine
from synth_data_creator.db.schema_init import initialize_schema, verify_schema
from synth_data_creator.generation.simulation import simulate_ecosystem
from synth_data_creator.generation.orchestrator import compute_db_kpis
from synth_data_creator.stats.kpi_calibration import calibrate_kpis

async def test():
    db_url = "postgresql+asyncpg://sugarcube:SugarCube%2308@localhost:5432/ir_econiq"
    engine = create_db_engine(db_url)
    await initialize_schema(engine, drop_existing=True)
    await verify_schema(engine)
    
    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)
    
    sim_results = await simulate_ecosystem(
        engine=engine,
        num_customers=500,
        start_date=start_date,
        end_date=end_date,
        seed=42,
        target_sales=150000,
        target_payments=150000,
        target_rgs=35000,
        batch_size=5000
    )
    
    kpis = await compute_db_kpis(engine, start_date, end_date)
    print("CRITICAL SIMULATION KPIS:")
    for k, v in kpis.items():
        print(f"  {k}: {v}")
        
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
    print("CALIBRATION CHECKS:")
    for k, v in calib["checks"].items():
        print(f"  {k}: {v}")
    print("ALL PASSED:", calib["all_passed"])
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test())
