Apply SQL (in order):
```sql
psql -d salam -f sql/00_schema.sql
psql -d salam -f sql/01_txn_source_parent.sql
psql -d salam -f sql/02_txn_source_partitions_maint.sql
psql -d salam -f sql/10_templates.sql
psql -d salam -f sql/20_staging.sql
psql -d salam -f sql/30_ledger.sql
psql -d salam -f sql/40_reporting.sql

```
Prepare partitions
```sql
psql -d salam -c "CALL public.rotate_txn_source_partitions(1,1);"

```

Ingest monthly txn_source (ensure txn_month precomputed):
```sql
-- fastest if you COPY to the child; parent also works.
\copy public.txn_source_202510 FROM 'oct2025.csv' CSV HEADER

```

Seed templates (use the insert examples we discussed — premium & claims).

Run:
```text
export PG_DSN=postgresql://user:pass@host:5432/salam
python -m python.run_month

```
