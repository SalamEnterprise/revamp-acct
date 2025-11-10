import polars as pl
from time import time
from .config import CREATED_BY
from .staging import stage_to_db
from .engine import expand_transactions
from .posting import post_to_ledger
from .balances import update_month_balance
from .db import get_conn

def timed(label, fn, *a, **k):
    t0 = time(); out = fn(*a, **k); t1 = time()
    print(f"{label:40s} {t1-t0:6.2f} sec"); return out

def load_txn_for_month(year, month):
    # Fast path: SELECT by month (partition pruning)
    with get_conn() as conn:
        return pl.read_database(
            f"""
            SELECT source_rowid, txn_type, product_code, channel, bank_value_date,
                   gross_amount, tabarru_amount, tanahud_amount, invest_amount, ujroh_amount, admin_amount
            FROM public.txn_source_parent
            WHERE txn_month = '{year:04d}-{month:02d}-01'
            """,
            connection=conn
        )

def run_pipeline(year: int, month: int):
    print("==== PIPELINE START ====")
    df_txn = timed("Load txn_source (month)", load_txn_for_month, year, month)

    headers, lines, run_id = timed("Polars journal expansion", expand_transactions, df_txn, CREATED_BY)
    timed("Stage to DB (COPY)", stage_to_db, headers, lines)

    timed("Post to ledger", post_to_ledger, headers, lines, year, month)
    timed("Update balances", update_month_balance, year, month)
    print("==== PIPELINE COMPLETE ====")

if __name__ == "__main__":
    run_pipeline(2025, 10)
