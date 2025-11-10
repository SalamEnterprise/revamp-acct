import uuid
import polars as pl
from datetime import date
from .expr import to_polars
from .templates import load_active_template

def expand_transactions(df_txn: pl.DataFrame, created_by: str) -> tuple[pl.DataFrame, pl.DataFrame, str]:
    """
    df_txn columns: source_rowid, txn_type, product_code, channel, bank_value_date,
                    gross_amount, tabarru_amount, tanahud_amount, invest_amount, ujroh_amount, admin_amount
    Returns: (headers_df, lines_df, run_id)
    """
    run_id = str(uuid.uuid4())

    # Assume single txn_type / month per batch (as per our flow).
    if df_txn.height == 0:
        return pl.DataFrame(), pl.DataFrame(), run_id

    # For routing we only need any row’s product/channel/date; templates are generic per batch.
    any_row = df_txn.select(["txn_type","product_code","channel","bank_value_date"]).row(0, named=True)
    tpl = load_active_template(any_row["txn_type"], any_row["product_code"], any_row["channel"], any_row["bank_value_date"])

    # Build JE numbers (deterministic for batch): e.g., "{YYYYMM}-{rowid}"
    df_txn = df_txn.with_columns([
        pl.col("bank_value_date").dt.strftime("%Y%m").alias("_yyyymm"),
        (pl.lit("JE-") + pl.col("_yyyymm") + "-" + pl.col("source_rowid")).alias("je_number"),
        pl.col("bank_value_date").alias("je_date")
    ]).drop("_yyyymm")

    # Headers
    headers = df_txn.select([
        pl.col("je_number"),
        pl.col("je_date"),
        pl.lit("JE").alias("je_type"),
        pl.col("source_rowid"),
        pl.lit(tpl["template_code"]).alias("template_code"),
        pl.lit(tpl["template_version"]).alias("template_version"),
        pl.lit(run_id).alias("run_id"),
        pl.lit(created_by).alias("created_by")
    ])
    # Lines: for each template line, compute amount expr over df_txn
    df_cols = set(df_txn.columns)
    line_frames = []
    for rec in tpl["lines"].to_dicts():
        if not rec["is_active"]:
            continue
        amt_expr = to_polars(rec["amount_expr"], df_cols)
        # Conditional enablement
        enabled = True
        if tpl["conds"].height:
            conds = tpl["conds"].filter(pl.col("line_no")==rec["line_no"])
            if conds.height:
                # combine with AND
                exprs = []
                for c in conds.to_dicts():
                    exprs.append(to_polars(c["cond_expr"], df_cols))
                cond_all = exprs[0]
                for e in exprs[1:]:
                    cond_all = cond_all & e
                line_df = df_txn.with_columns(cond_all.alias("__enabled"))
                enabled = None
        # build base
        base = df_txn.select([
            pl.col("je_number"),
            pl.lit(rec["line_no"]).alias("line_no"),
            pl.lit(rec["side"]).alias("side"),
            pl.lit(rec["account_code"]).alias("account_code"),
            pl.lit(rec["fund_code"]).alias("fund"),
            amt_expr.alias("amount"),
            pl.col("product_code"), pl.col("channel"),
            pl.col("je_date"),
        ])
        if tpl["conds"].height:
            # recompute to include enabled mask
            conds = tpl["conds"].filter(pl.col("line_no")==rec["line_no"])
            if conds.height:
                exprs = [to_polars(c["cond_expr"], df_cols) for c in conds.to_dicts()]
                cond_all = exprs[0]
                for e in exprs[1:]:
                    cond_all = cond_all & e
                base = base.with_columns(cond_all.alias("__enabled")).filter(pl.col("__enabled")==True).drop("__enabled")

        # rounding & drop zero
        base = base.with_columns(pl.col("amount").round(rec["amount_round"]))
        base = base.filter(pl.col("amount") != 0)
        line_frames.append(base)

    lines = pl.concat(line_frames) if line_frames else pl.DataFrame()
    # Attach template + run
    lines = lines.with_columns([
        pl.lit(tpl["template_code"]).alias("template_code"),
        pl.lit(tpl["template_version"]).alias("template_version"),
        pl.lit(run_id).alias("run_id")
    ])
    # DR/CR sign not applied; we keep side separate

    # Optional DR=CR validation per template control (quick check)
    ctrl = tpl["control"]
    if ctrl.get("require_balanced", True) and lines.height:
        by_je = (
            lines.group_by("je_number","side")
                 .agg(pl.col("amount").sum().alias("amt"))
                 .pivot(values="amt", index=["je_number"], on="side")
                 .with_columns([
                     (pl.col("DR").fill_null(0) - pl.col("CR").fill_null(0)).alias("_diff")
                 ])
        )
        max_unbal = abs(by_je.select(pl.col("_diff").abs().max()).item())
        if max_unbal > float(ctrl.get("tolerance_amount", 0.01)):
            raise ValueError(f"Unbalanced JE detected; max diff={max_unbal}")

    return headers, lines, run_id
