from datetime import date
from dateutil.relativedelta import relativedelta
from .db import get_conn

def update_month_balance(year: int, month: int):
    start_date = date(year, month, 1)
    end_date   = start_date + relativedelta(months=1)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            WITH mvt AS (
              SELECT l.account_code, l.fund,
                     SUM(CASE WHEN l.side='DR' THEN l.amount ELSE 0 END) AS debit,
                     SUM(CASE WHEN l.side='CR' THEN l.amount ELSE 0 END) AS credit
              FROM public.ledger_entry_line l
              JOIN public.ledger_entry_header h ON h.je_id = l.je_id
              WHERE h.je_date >= %s AND h.je_date < %s
              GROUP BY l.account_code, l.fund
            )
            INSERT INTO public.account_balance_snapshot
              (period_start, account_code, fund, opening_balance, debit, credit, closing_balance, calculated_at)
            SELECT %s, m.account_code, m.fund, 0, m.debit, m.credit, (0 + m.debit - m.credit), now()
            ON CONFLICT (period_start, account_code, fund) DO UPDATE
            SET debit = EXCLUDED.debit, credit = EXCLUDED.credit,
                closing_balance = EXCLUDED.closing_balance,
                calculated_at = now();
        """, (start_date, end_date, start_date))
