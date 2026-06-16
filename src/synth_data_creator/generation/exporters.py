import os
import csv
import uuid
import random
from datetime import date, datetime
from typing import Any, Dict, List
import polars as pl
import numpy as np


# --- Phase A: Dirty Data Injection Engine ---

def inject_dirty_identities(customers: List[Dict[str, Any]], duplication_rate: float, rng: np.random.Generator) -> List[Dict[str, Any]]:
    """Intentionally creates duplicates and slight spelling variations for B2B names."""
    corrupted_customers = []
    
    for cust in customers:
        # Keep original
        corrupted_customers.append(cust)
        
        # Determine if we duplicate this identity
        if rng.random() < duplication_rate:
            # Create duplicates
            name = cust["business_name"]
            # Variations: Sharma Textiles -> Sharma Textile, Sharma Tex, Sharma Textiles Pvt Ltd, etc.
            words = name.split()
            base_word = words[0] if words else "Company"
            
            variations = [
                f"{name} Pvt Ltd",
                f"{name} Store",
                f"{base_word} Textiles",
                f"{base_word} Textile",
                f"{base_word} Tex",
                f"{name} & Sons",
                f"{name} Retail"
            ]
            chosen_variation = rng.choice(variations)
            
            dup_cust = cust.copy()
            dup_cust["id"] = uuid.uuid4() # Different UUID representing duplicate identity
            dup_cust["business_name"] = chosen_variation
            dup_cust["customer_code"] = f"{cust['customer_code']}-DUP"
            # Omit Phone/Email on duplicates to simulate missing fields
            dup_cust["phone"] = ""
            dup_cust["email"] = ""
            
            corrupted_customers.append(dup_cust)
            
    return corrupted_customers


def corrupt_fields_and_formats(records: List[Dict[str, Any]], table_name: str, rng: np.random.Generator) -> List[Dict[str, Any]]:
    """Applies date formatting changes, random nulls, and malformed invoice/GST fields."""
    corrupted = []
    for rec in records:
        c_rec = rec.copy()
        
        # 1. Missing Fields (Phase A)
        if table_name == "customers":
            if rng.random() < 0.10:
                c_rec["phone"] = None
            if rng.random() < 0.10:
                c_rec["email"] = None
            if rng.random() < 0.05:
                c_rec["postal_code"] = None
        elif table_name == "raw_sales":
            if rng.random() < 0.05:
                c_rec["due_date"] = None
        elif table_name == "raw_payments":
            if rng.random() < 0.08:
                c_rec["reference_number"] = None
                
        # 2. Formatting inconsistencies (Phase A)
        if table_name == "customers":
            # GST Format variations
            gstin = f"27{rng.choice(['A','B','C','D'])}{rng.choice(['P','C','F'])}{rng.integers(1000, 9999)}{rng.choice(['A','B'])}{rng.integers(1, 9)}Z{rng.integers(1, 9)}"
            if rng.random() < 0.05:
                c_rec["behavioral_profile"]["params"]["gst_number"] = gstin
            elif rng.random() < 0.05:
                c_rec["behavioral_profile"]["params"]["gst_number"] = f"GST-{gstin}"
            elif rng.random() < 0.05:
                # Malformed
                c_rec["behavioral_profile"]["params"]["gst_number"] = gstin[:8]
                
        # Date inconsistencies
        for date_field in ["registration_date", "order_date", "invoice_date", "due_date", "payment_date", "return_date"]:
            if date_field in c_rec and c_rec[date_field]:
                d_val = c_rec[date_field]
                if isinstance(d_val, (date, datetime)):
                    r = rng.random()
                    if r < 0.05:
                        # Format 01/05/2025
                        c_rec[date_field] = d_val.strftime("%d/%m/%Y")
                    elif r < 0.10:
                        # Format 1-May-2025
                        c_rec[date_field] = d_val.strftime("%d-%b-%Y")
                    else:
                        c_rec[date_field] = d_val.isoformat()

        # 3. Invoice Corruption
        if table_name == "raw_sales":
            if rng.random() < 0.02:
                # Skipped or malformed invoice ID
                c_rec["invoice_number"] = f"MAL-{rng.integers(100, 999)}"

        corrupted.append(c_rec)
    return corrupted


# --- Exporter Layer ---

def export_all_modes(data: Dict[str, Any], output_dir: str, duplication_rate: float, seed: int) -> None:
    os.makedirs(output_dir, exist_ok=True)
    rng = np.random.default_rng(seed)

    # Mode 1: Event Log
    print(f"Exporting Mode 1 (Event Logs) to {output_dir}/event_logs.csv...", flush=True)
    export_to_csv(data["event_logs"], os.path.join(output_dir, "event_logs.csv"))

    # Mode 2: Reconciled Materialized Tables
    print(f"Exporting Mode 2 (Relational Tables) to {output_dir}...", flush=True)
    export_to_csv(data["customers"], os.path.join(output_dir, "customers_clean.csv"))
    export_to_csv(data["raw_sales"], os.path.join(output_dir, "raw_sales_clean.csv"))
    export_to_csv(data["raw_payments"], os.path.join(output_dir, "raw_payments_clean.csv"))
    export_to_csv(data["raw_returns"], os.path.join(output_dir, "raw_returns_clean.csv"))

    # Mode 3: Dirty ERP CSVs (Tally, BUSY, Marg ERP)
    print(f"Exporting Mode 3 (Dirty ERP CSVs) to {output_dir}...", flush=True)
    dirty_cust = inject_dirty_identities(data["customers"], duplication_rate, rng)
    dirty_cust = corrupt_fields_and_formats(dirty_cust, "customers", rng)
    dirty_sales = corrupt_fields_and_formats(data["raw_sales"], "raw_sales", rng)
    dirty_payments = corrupt_fields_and_formats(data["raw_payments"], "raw_payments", rng)
    
    export_to_csv(dirty_cust, os.path.join(output_dir, "tally_customers.csv"))
    export_to_csv(dirty_sales, os.path.join(output_dir, "busy_sales.csv"))
    export_to_csv(dirty_payments, os.path.join(output_dir, "marg_payments.csv"))

    # Mode 4: Feature Store Snapshot (Polars computations)
    print(f"Exporting Mode 4 (Feature Store Snapshot) to {output_dir}/features_snapshot.csv...", flush=True)
    export_feature_store_snapshot(data, os.path.join(output_dir, "features_snapshot.csv"))

    # Mode 5: Benchmark Dataset
    print(f"Exporting Mode 5 (Benchmarks) to {output_dir}/benchmarks.csv...", flush=True)
    export_to_csv(data["intelligence_benchmarks"], os.path.join(output_dir, "benchmarks.csv"))


def export_to_csv(records: List[Dict[str, Any]], filepath: str) -> None:
    if not records:
        return
    keys = records[0].keys()
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in records:
            writer.writerow(row)


def export_feature_store_snapshot(data: Dict[str, Any], filepath: str) -> None:
    """Uses Polars to compute rolling feature store snapshots for all customers."""
    if not data["raw_sales"]:
        return

    # Convert all UUID fields to str to avoid Polars object type comparison issues
    sales_clean = []
    for s in data["raw_sales"]:
        s_copy = s.copy()
        s_copy["customer_id"] = str(s_copy["customer_id"])
        s_copy["id"] = str(s_copy["id"])
        sales_clean.append(s_copy)

    payments_clean = []
    for p in data["raw_payments"]:
        p_copy = p.copy()
        p_copy["customer_id"] = str(p_copy["customer_id"])
        p_copy["invoice_id"] = str(p_copy["invoice_id"])
        payments_clean.append(p_copy)

    # Load into Polars DataFrames
    df_sales = pl.DataFrame(sales_clean)
    df_payments = pl.DataFrame(payments_clean) if payments_clean else pl.DataFrame(schema={
        "customer_id": pl.String, "payment_amount": pl.Float64, "payment_date": pl.Object
    })
    
    # Cast dates
    df_sales = df_sales.with_columns(pl.col("invoice_date").cast(pl.Date))
    if payments_clean:
        df_payments = df_payments.with_columns(pl.col("payment_date").cast(pl.Date))

    # Aggregate features per customer
    features = []
    customer_ids = [c["id"] for c in data["customers"]]

    for cid in customer_ids:
        cid_str = str(cid)
        # Sales slices
        c_sales = df_sales.filter(pl.col("customer_id") == cid_str)
        c_payments = df_payments.filter(pl.col("customer_id") == cid_str)

        sales_count = len(c_sales)
        total_invoiced = c_sales["invoice_amount"].sum() if sales_count > 0 else 0.0
        total_paid = c_sales["amount_paid"].sum() if sales_count > 0 else 0.0
        outstanding = c_sales["balance_due"].sum() if sales_count > 0 else 0.0
        
        # Payment delay (average delay)
        # Reconstruct delay if payment records exist
        avg_delay = 0.0
        if not c_payments.is_empty():
            # Join sales & payments
            c_sales_slim = c_sales.select(["id", "invoice_date"])
            joined = c_payments.join(c_sales_slim, left_on="invoice_id", right_on="id")
            if not joined.is_empty():
                joined = joined.with_columns((pl.col("payment_date") - pl.col("invoice_date")).dt.total_days().alias("delay"))
                avg_delay = joined["delay"].mean() or 0.0

        features.append({
            "customer_id": str(cid),
            "total_sales_count": sales_count,
            "total_invoiced_amount": total_invoiced,
            "total_paid_amount": total_paid,
            "total_outstanding_amount": outstanding,
            "average_payment_delay_days": round(avg_delay, 2),
            "outstanding_ratio": round(outstanding / total_invoiced if total_invoiced > 0 else 0.0, 4),
            "collection_efficiency": round(total_paid / total_invoiced if total_invoiced > 0 else 0.0, 4),
        })

    df_features = pl.DataFrame(features)
    df_features.write_csv(filepath)
