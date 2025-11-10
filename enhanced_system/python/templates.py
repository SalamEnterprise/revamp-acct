import polars as pl
from .db import get_conn

def load_active_template(txn_type: str, product_code: str, channel: str, txn_date) -> dict:
    sql = """
    SELECT m.match_id, t.template_code, t.template_version, t.description_pattern, t.je_type
    FROM acct.journal_template t
    JOIN acct.journal_template_match m
      ON m.template_code=t.template_code AND m.template_version=t.template_version
    WHERE t.txn_type=%s AND t.status='ACTIVE'
      AND t.effective_date <= %s AND t.expiry_date > %s
      AND (m.product_code = %s OR m.product_code IS NULL)
      AND (m.channel = %s OR m.channel IS NULL)
    ORDER BY m.priority ASC, (m.product_code IS NULL)::int, (m.channel IS NULL)::int
    LIMIT 1;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (txn_type, txn_date, txn_date, product_code, channel))
        row = cur.fetchone()
        if not row:
            raise RuntimeError("No active template matched.")
        template_code, template_version = row[1], row[2]

    # load lines & control & conditions
    with get_conn() as conn:
        lines = pl.read_database(
            f"""
            SELECT line_no, side, account_code, fund_code, amount_expr, amount_round, is_active
            FROM acct.journal_template_line
            WHERE template_code = '{template_code}' AND template_version = '{template_version}'
            ORDER BY line_no
            """,
            connection=conn
        )
        conds = pl.read_database(
            f"""
            SELECT line_no, cond_name, cond_expr
            FROM acct.journal_template_line_cond
            WHERE template_code = '{template_code}' AND template_version = '{template_version}'
            """,
            connection=conn
        )
        ctrl = pl.read_database(
            f"""
            SELECT require_balanced, tolerance_amount, balancing_mode, balancing_account, balancing_fund
            FROM acct.journal_template_control
            WHERE template_code = '{template_code}' AND template_version = '{template_version}'
            """,
            connection=conn
        )
    return {
        "template_code": template_code,
        "template_version": template_version,
        "lines": lines,
        "conds": conds,
        "control": ctrl.to_dicts()[0] if ctrl.height else
                   {"require_balanced": True, "tolerance_amount": 0.01, "balancing_mode": "ERROR",
                    "balancing_account": None, "balancing_fund": None}
    }
