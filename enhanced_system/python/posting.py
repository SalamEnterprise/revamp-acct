import polars as pl
from datetime import date
from dateutil.relativedelta import relativedelta
from .db import get_conn, copy_from_polars

def post_to_ledger(headers: pl.DataFrame, lines: pl.DataFrame, year: int, month: int):
    start_date = date(year, month, 1)
    end_date = start_date + relativedelta(months=1)

    with get_conn() as conn:
        # 1) Insert headers via COPY → je_id auto
        copy_from_polars(conn, headers.select([
            "je_number","je_date","je_type","source_rowid","template_code","template_version","run_id"
        ]), "public.ledger_entry_header")

        # 2) Fetch je_number→je_id map
        df_map = pl.read_database(
            f"""
            SELECT je_number, je_id
            FROM public.ledger_entry_header
            WHERE je_date >= '{start_date}' AND je_date < '{end_date}'
            """, connection=conn
        )

        # 3) Join in Polars, sort by je_date (helps partition routing)
        df_lines = (
            lines.join(df_map, on="je_number", how="inner")
                 .select(["je_id","line_no","side","account_code","fund","amount","je_date"])
                 .sort("je_date")
        )

        # 4) Ensure target partition exists
        with conn.cursor() as cur:
            cur.execute("SELECT public.ensure_ledger_line_partition(%s)", (start_date,))

        # 5) COPY into ledger lines
        copy_from_polars(conn, df_lines, "public.ledger_entry_line")

        # 6) Mark staging as posted (by run_id)
        run_id = headers.select("run_id").unique().item()
        with conn.cursor() as cur:
            cur.execute("UPDATE public.je_header_staging SET posted=TRUE, posted_at=now() WHERE run_id=%s", (run_id,))
            cur.execute("UPDATE public.je_line_staging   SET posted=TRUE, posted_at=now() WHERE run_id=%s", (run_id,))
