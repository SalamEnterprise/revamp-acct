import polars as pl
import numpy as np
from datetime import date, timedelta
from time import time
from .db import get_conn, copy_from_polars


def seed_txn_source(year=2025, month=10, n_rows=1_000_000, created_by="system"):
    """
    Generate and insert n_rows transactions for one month into txn_source_parent.
    Investment fund = gross - tabarru - tanahud - ujroh - admin.
    """

    t0 = time()
    start_date = date(year, month, 1)
    next_month = date(year + (month // 12), (month % 12) + 1, 1)
    n_days = (next_month - start_date).days

    np.random.seed(42)  # deterministic for reproducibility

    # --- Base attributes -----------------------------------------------------
    txn_type = np.random.choice(["PREMIUM_RECEIPT", "CLAIM_PAID"], size=n_rows, p=[0.8, 0.2])
    product_code = np.random.choice(["LIFE01", "FAM01", "INV01"], size=n_rows, p=[0.6, 0.3, 0.1])
    channel = np.random.choice(["AGENCY", "INBRANCH"], size=n_rows, p=[0.7, 0.3])
    bank_value_date = np.array([
        start_date + timedelta(days=int(x))
        for x in np.random.randint(0, n_days, size=n_rows)
    ])
    txn_month = np.array([d.replace(day=1) for d in bank_value_date])
    gross_amount = np.random.uniform(100_000, 5_000_000, size=n_rows).round(2)

    # --- Components for PREMIUM_RECEIPT -------------------------------------
    tabarru_ratio = np.random.uniform(0.2, 0.4, size=n_rows)
    tanahud_ratio = np.random.uniform(0.05, 0.15, size=n_rows)
    ujroh_ratio   = np.random.uniform(0.05, 0.1, size=n_rows)
    admin_ratio   = np.random.uniform(0.01, 0.05, size=n_rows)

    tabarru_amount = (gross_amount * tabarru_ratio).round(2)
    tanahud_amount = (gross_amount * tanahud_ratio).round(2)
    ujroh_amount   = (gross_amount * ujroh_ratio).round(2)
    admin_amount   = (gross_amount * admin_ratio).round(2)

    # Residual investment fund
    invest_amount  = (
        gross_amount - tabarru_amount - tanahud_amount - ujroh_amount - admin_amount
    ).round(2)

    # --- Adjust for CLAIM_PAID transactions ---------------------------------
    claim_mask = txn_type == "CLAIM_PAID"
    if claim_mask.any():
        # For claims: gross = tabarru + invest - admin (no tanahud, no ujroh)
        tabarru_amount[claim_mask] = (gross_amount[claim_mask] * 0.8).round(2)
        admin_amount[claim_mask]   = (gross_amount[claim_mask] * 0.02).round(2)
        tanahud_amount[claim_mask] = 0
        ujroh_amount[claim_mask]   = 0
        invest_amount[claim_mask]  = (
            gross_amount[claim_mask] - tabarru_amount[claim_mask] + admin_amount[claim_mask]
        ).round(2)
        # Adjust gross to match accounting rule exactly
        gross_amount[claim_mask] = (
            tabarru_amount[claim_mask] + invest_amount[claim_mask] - admin_amount[claim_mask]
        ).round(2)

    # --- Build final Polars DataFrame ---------------------------------------
    df = pl.DataFrame({
        "source_rowid": [f"TXN-{i+1:07d}" for i in range(n_rows)],
        "txn_type": txn_type,
        "policy_no": [f"POL-{np.random.randint(1_000_000):06d}" for _ in range(n_rows)],
        "product_code": product_code,
        "channel": channel,
        "bank_value_date": bank_value_date,
        "txn_month": txn_month,
        "currency": ["IDR"] * n_rows,
        "gross_amount": gross_amount,
        "tabarru_amount": tabarru_amount,
        "tanahud_amount": tanahud_amount,
        "invest_amount": invest_amount,
        "ujroh_amount": ujroh_amount,
        "admin_amount": admin_amount,
    })

    # --- Ensure monthly partition exists ------------------------------------
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT public.ensure_txn_source_partition(%s)", (start_date,))

    # --- Fast COPY to PostgreSQL --------------------------------------------
    with get_conn() as conn:
        copy_from_polars(conn, df, "public.txn_source_parent")

    t1 = time()
    print(f"Seeded {n_rows:,} rows for {year}-{month:02d} in {t1 - t0:6.2f} sec")

    return df.head(5)
