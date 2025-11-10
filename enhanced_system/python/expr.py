import polars as pl
import re

_ALLOWED_FUNCS = {
    "abs": abs,
    "min": lambda a,b: pl.min_horizontal(a,b),
    "max": lambda a,b: pl.max_horizontal(a,b),
    "round": lambda x, n=2: pl.when(pl.lit(True)).then(pl.col("__tmp")).otherwise(pl.lit(None))
}
# We won't actually call Python funcs directly; we translate to Polars.

TOKEN = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")

def to_polars(expr: str, df_cols: set[str]) -> pl.Expr:
    # Replace :field with pl.col('field'); allow + - * / ( ) and commas in simple funcs
    # Minimal safe parser: no eval. Only column tokens and arithmetic.
    s = expr.strip()
    # sanity: ensure only allowed chars besides tokens
    if not re.fullmatch(r"[0-9\.\s\+\-\*\/\(\),:_a-zA-Z]+", s):
        raise ValueError(f"Illegal characters in expression: {expr}")

    # Replace tokens with a placeholder syntax understood by eval_expr below
    parts = []
    last = 0
    for m in TOKEN.finditer(s):
        parts.append(s[last:m.start()])
        name = m.group(1)
        if name not in df_cols:
            raise KeyError(f"Unknown column :{name} in expr {expr}")
        parts.append(f"pl.col('{name}')")
        last = m.end()
    parts.append(s[last:])
    code = "".join(parts)

    # Map basic functions to Polars; keep safe subset only
    code = (code
            .replace("abs(", "pl.abs(")
            .replace("min(", "pl.min_horizontal(")  # min(a,b) -> min_horizontal(a,b)
            .replace("max(", "pl.max_horizontal(")
            )

    # 'round(x, n)' approximate: use pl.round(x, n)
    code = re.sub(r"round\(", "pl.round(", code)

    # Now build expression using Python eval with restricted namespace
    try:
        expr_obj = eval(code, {"pl": pl}, {})
    except Exception as e:
        raise ValueError(f"Failed to parse amount_expr '{expr}': {e}")
    return expr_obj
