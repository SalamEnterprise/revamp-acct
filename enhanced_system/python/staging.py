import polars as pl
from .db import get_conn, copy_from_polars

def stage_to_db(headers: pl.DataFrame, lines: pl.DataFrame):
    with get_conn() as conn:
        copy_from_polars(conn, headers.select([
            "je_number","je_date","je_type","source_rowid",
            "template_code","template_version","run_id","created_by"
        ]), "public.je_header_staging")
        copy_from_polars(conn, lines.select([
            "run_id","je_number","line_no","side","account_code","fund","amount",
            "product_code","channel","je_date","template_code","template_version"
        ]), "public.je_line_staging")
