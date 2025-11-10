import psycopg
from contextlib import contextmanager
from .config import PG_DSN

@contextmanager
def get_conn():
    with psycopg.connect(PG_DSN) as conn:
        yield conn

def copy_from_polars(conn, df, table_name):
    # Writes a Polars DataFrame to PostgreSQL via COPY (CSV in-memory)
    import io
    csv_buf = io.StringIO()
    df.write_csv(csv_buf)
    csv_buf.seek(0)
    cols = ",".join(df.columns)
    with conn.cursor() as cur:
        cur.execute(f"COPY {table_name} ({cols}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)")
        cur.copy(csv_buf.read())
