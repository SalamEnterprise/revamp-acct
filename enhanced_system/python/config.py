import os

PG_DSN = os.getenv("PG_DSN", "postgresql://user:pass@localhost:5432/salam")
CREATED_BY = os.getenv("CREATED_BY", "acct-engine")
