# DDL — Schemas & reference

---

### txn_source_parent.sql

```sql
-- Parent, partitioned by txn_month (precomputed in ETL/Polars)
DROP TABLE IF EXISTS public.txn_source_parent CASCADE;

CREATE TABLE public.txn_source_parent (
    source_rowid        varchar(32) NOT NULL,
    txn_type            varchar(50) NOT NULL,        -- 'PREMIUM_RECEIPT' | 'CLAIM_PAID'
    policy_no           varchar(30),
    product_code        varchar(50),
    channel             varchar(50),
    bank_value_date     date NOT NULL,
    txn_month           date NOT NULL,               -- precomputed: date_trunc('month', bank_value_date)
    currency            varchar(10) DEFAULT 'IDR',
    gross_amount        numeric(20,6) NOT NULL,
    tabarru_amount      numeric(20,6) DEFAULT 0,
    tanahud_amount      numeric(20,6) DEFAULT 0,
    invest_amount       numeric(20,6) DEFAULT 0,
    ujroh_amount        numeric(20,6) DEFAULT 0,
    admin_amount        numeric(20,6) DEFAULT 0,
    is_premium          bool GENERATED ALWAYS AS (txn_type = 'PREMIUM_RECEIPT') STORED,
    is_claim            bool GENERATED ALWAYS AS (txn_type = 'CLAIM_PAID') STORED,
    created_at          timestamptz DEFAULT now(),
    CONSTRAINT chk_takaful_balance CHECK (
        CASE
            WHEN txn_type = 'PREMIUM_RECEIPT'
                THEN gross_amount = tabarru_amount + tanahud_amount + invest_amount + ujroh_amount + admin_amount
            WHEN txn_type = 'CLAIM_PAID'
                THEN gross_amount = tabarru_amount + invest_amount - admin_amount
            ELSE TRUE
        END
    ),
    CONSTRAINT txn_source_parent_pkey PRIMARY KEY (txn_month, source_rowid)
) PARTITION BY RANGE (txn_month);

```

### txn_source_partitions_maint.sql

```sql
-- Create one month partition (idempotent) + local indexes + analyze
CREATE OR REPLACE FUNCTION public.ensure_txn_source_partition(p_month date)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
  start_month date := date_trunc('month', p_month)::date;
  next_month  date := (date_trunc('month', p_month) + interval '1 month')::date;
  part_name   text := format('txn_source_%s', to_char(start_month,'YYYYMM'));
  exists_part boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname=part_name
  ) INTO exists_part;

  IF NOT exists_part THEN
    EXECUTE format(
      'CREATE TABLE public.%I PARTITION OF public.txn_source_parent
         FOR VALUES FROM (%L) TO (%L);',
      part_name, start_month, next_month
    );
    -- Indexes: fast range + common filters
    EXECUTE format('CREATE INDEX %I_brin_bankdate ON public.%I USING BRIN (bank_value_date);', part_name, part_name);
    EXECUTE format('CREATE INDEX %I_ix_product ON public.%I (product_code);', part_name, part_name);
    EXECUTE format('CREATE INDEX %I_ix_channel ON public.%I (channel);', part_name, part_name);
  END IF;

  EXECUTE format('ANALYZE public.%I;', part_name);
  RETURN part_name;
END;
$$;

-- Rotate a window of months around 'today' (previous..next)
CREATE OR REPLACE PROCEDURE public.rotate_txn_source_partitions(ahead int DEFAULT 1, behind int DEFAULT 1)
LANGUAGE plpgsql AS $$
DECLARE
  base date := date_trunc('month', current_date)::date;
  i int; target date;
BEGIN
  FOR i IN REVERSE 1..behind LOOP
    target := (base - (i || ' months')::interval)::date;
    PERFORM public.ensure_txn_source_partition(target);
  END LOOP;
  PERFORM public.ensure_txn_source_partition(base);
  FOR i IN 1..ahead LOOP
    target := (base + (i || ' months')::interval)::date;
    PERFORM public.ensure_txn_source_partition(target);
  END LOOP;
END; $$;

-- Purge old month partitions (drop, or swap with parquet archive before dropping)
CREATE OR REPLACE PROCEDURE public.purge_old_txn_source_partitions(retention_months int DEFAULT 12)
LANGUAGE plpgsql AS $$
DECLARE
  cutoff date := (date_trunc('month', current_date) - (retention_months || ' months')::interval)::date;
  r record; part_month date;
BEGIN
  FOR r IN
    SELECT c.relname AS part_name
    FROM pg_inherits i
    JOIN pg_class c ON c.oid = i.inhrelid
    JOIN pg_class p ON p.oid = i.inhparent
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname='public' AND p.relname='txn_source_parent'
  LOOP
    BEGIN
      part_month := to_date(substring(r.part_name from '([0-9]{6})$'),'YYYYMM');
    EXCEPTION WHEN others THEN part_month := NULL; END;

    IF part_month IS NOT NULL AND part_month < cutoff THEN
      EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE;', r.part_name);
      RAISE NOTICE 'Dropped old txn_source partition: %', r.part_name;
    END IF;
  END LOOP;
END; $$;

```

### templates.sql

```sql
-- Template header
CREATE TABLE IF NOT EXISTS acct.journal_template (
  template_code        varchar(50)  NOT NULL,
  template_version     varchar(20)  NOT NULL,
  title                varchar(200) NOT NULL,
  txn_type             varchar(50)  NOT NULL,
  description_pattern  text         NOT NULL,
  je_type              varchar(50)  NOT NULL,
  effective_date       date         NOT NULL,
  expiry_date          date         NOT NULL DEFAULT '9999-12-31',
  status               varchar(20)  NOT NULL DEFAULT 'ACTIVE', -- ACTIVE/DRAFT/RETIRED
  created_by           varchar(100) NOT NULL,
  created_at           timestamp    NOT NULL DEFAULT now(),
  approved_by          varchar(100),
  approved_at          timestamp,
  CONSTRAINT journal_template_pk PRIMARY KEY (template_code, template_version)
);

CREATE INDEX IF NOT EXISTS idx_jt_txn_type_eff
  ON acct.journal_template (txn_type, status, effective_date, expiry_date);

-- Routing rules (NULL = wildcard). Surrogate PK to allow NULLs.
CREATE TABLE IF NOT EXISTS acct.journal_template_match (
  match_id             bigserial PRIMARY KEY,
  template_code        varchar(50)  NOT NULL,
  template_version     varchar(20)  NOT NULL,
  product_code         varchar(50),     -- NULL = wildcard
  channel              varchar(50),     -- NULL = wildcard
  min_amount           numeric(20,6),
  max_amount           numeric(20,6),
  condition_expr       text,            -- boolean expression over txn_source fields
  priority             int NOT NULL DEFAULT 100,
  CONSTRAINT jt_match_fk FOREIGN KEY (template_code, template_version)
    REFERENCES acct.journal_template(template_code, template_version) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jt_match_route
  ON acct.journal_template_match (template_code, product_code, channel, priority);

-- Posting lines
CREATE TABLE IF NOT EXISTS acct.journal_template_line (
  template_code        varchar(50)  NOT NULL,
  template_version     varchar(20)  NOT NULL,
  line_no              int          NOT NULL,
  side                 char(2)      NOT NULL CHECK (side IN ('DR','CR')),
  account_code         varchar(50)  NOT NULL,
  fund_code            varchar(10)  NOT NULL,            -- OP/TBR/TNH/INV
  amount_expr          text         NOT NULL,            -- e.g. ':tabarru_amount'
  amount_round         int          NOT NULL DEFAULT 2,
  is_active            boolean      NOT NULL DEFAULT TRUE,
  note                 text,
  CONSTRAINT jt_line_pk PRIMARY KEY (template_code, template_version, line_no),
  CONSTRAINT jt_line_fk FOREIGN KEY (template_code, template_version)
    REFERENCES acct.journal_template(template_code, template_version) ON DELETE CASCADE
);

-- Optional: conditional enablement of lines
CREATE TABLE IF NOT EXISTS acct.journal_template_line_cond (
  template_code        varchar(50)  NOT NULL,
  template_version     varchar(20)  NOT NULL,
  line_no              int          NOT NULL,
  cond_name            varchar(50)  NOT NULL,
  cond_expr            text         NOT NULL,
  CONSTRAINT jt_line_cond_pk PRIMARY KEY (template_code, template_version, line_no, cond_name),
  CONSTRAINT jt_line_cond_fk FOREIGN KEY (template_code, template_version, line_no)
    REFERENCES acct.journal_template_line(template_code, template_version, line_no) ON DELETE CASCADE
);

-- Balancing control per template
CREATE TABLE IF NOT EXISTS acct.journal_template_control (
  template_code        varchar(50)  NOT NULL,
  template_version     varchar(20)  NOT NULL,
  require_balanced     boolean      NOT NULL DEFAULT TRUE,
  tolerance_amount     numeric(20,6) NOT NULL DEFAULT 0.01,
  balancing_mode       varchar(20)  NOT NULL DEFAULT 'ERROR', -- ERROR | AUTO_ADJUST
  balancing_account    varchar(50),
  balancing_fund       varchar(10),
  CONSTRAINT jt_ctrl_pk PRIMARY KEY (template_code, template_version),
  CONSTRAINT jt_ctrl_fk FOREIGN KEY (template_code, template_version)
    REFERENCES acct.journal_template(template_code, template_version) ON DELETE CASCADE
);

```

### staging.sql (UNLOGGED, minimal indexes)

```sql
-- Headers
DROP TABLE IF EXISTS public.je_header_staging;
CREATE UNLOGGED TABLE public.je_header_staging (
  je_internal_id   bigserial PRIMARY KEY,
  run_id           uuid NOT NULL,
  je_number        varchar(30) NOT NULL,
  je_date          date NOT NULL,
  je_type          varchar(50),
  source_rowid     varchar(32),
  template_code    varchar(50),
  template_version varchar(20),
  description      text,
  created_by       varchar(100),
  created_at       timestamp DEFAULT now(),
  posted           boolean DEFAULT FALSE,
  posted_at        timestamp
);
CREATE INDEX IF NOT EXISTS idx_je_hdr_stg_runid ON public.je_header_staging(run_id);

-- Lines
DROP TABLE IF EXISTS public.je_line_staging;
CREATE UNLOGGED TABLE public.je_line_staging (
  id               bigserial PRIMARY KEY,
  run_id           uuid NOT NULL,
  je_number        varchar(30) NOT NULL,
  line_no          int NOT NULL,
  side             char(2) NOT NULL,
  account_code     varchar(50) NOT NULL,
  fund             varchar(10) NOT NULL,
  amount           numeric(20,6) NOT NULL,
  product_code     varchar(50),
  channel          varchar(50),
  je_date          date NOT NULL,
  template_code    varchar(50),
  template_version varchar(20),
  created_at       timestamp DEFAULT now(),
  posted           boolean DEFAULT FALSE,
  posted_at        timestamp
);
CREATE INDEX IF NOT EXISTS idx_je_line_stg_runid ON public.je_line_staging(run_id);
CREATE INDEX IF NOT EXISTS idx_je_line_stg_je_number ON public.je_line_staging(je_number);

```

### Ledger (partitioned lines by month, fast posting)

```sql
-- Ledger headers (not partitioned)
DROP TABLE IF EXISTS public.ledger_entry_header CASCADE;
CREATE TABLE public.ledger_entry_header (
  je_id            bigserial PRIMARY KEY,
  je_number        varchar(30) UNIQUE NOT NULL,
  je_date          date NOT NULL,
  je_type          varchar(50),
  source_rowid     varchar(32),
  template_code    varchar(50),
  template_version varchar(20),
  run_id           uuid NOT NULL,
  posted_at        timestamp NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_leh_runid ON public.ledger_entry_header(run_id);
CREATE INDEX IF NOT EXISTS idx_leh_jedate ON public.ledger_entry_header(je_date);

-- Ledger lines (partitioned by je_date month)
DROP TABLE IF EXISTS public.ledger_entry_line CASCADE;
CREATE TABLE public.ledger_entry_line (
  id           bigserial PRIMARY KEY,
  je_id        bigint NOT NULL REFERENCES public.ledger_entry_header(je_id),
  line_no      int NOT NULL,
  side         char(2) NOT NULL CHECK (side IN ('DR','CR')),
  account_code varchar(50) NOT NULL,
  fund         varchar(10) NOT NULL,
  amount       numeric(20,6) NOT NULL,
  je_date      date NOT NULL
) PARTITION BY RANGE (je_date);

-- helper to create monthly partitions for lines
CREATE OR REPLACE FUNCTION public.ensure_ledger_line_partition(p_month date)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
  start_month date := date_trunc('month', p_month)::date;
  next_month  date := (date_trunc('month', p_month) + interval '1 month')::date;
  part_name   text := format('ledger_entry_line_%s', to_char(start_month,'YYYYMM'));
  exists_part boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname=part_name
  ) INTO exists_part;

  IF NOT exists_part THEN
    EXECUTE format(
      'CREATE TABLE public.%I PARTITION OF public.ledger_entry_line
         FOR VALUES FROM (%L) TO (%L);',
      part_name, start_month, next_month
    );
    EXECUTE format('CREATE INDEX %I_ix_acct_fund ON public.%I (account_code, fund);', part_name, part_name);
    EXECUTE format('CREATE INDEX %I_brin_jedate ON public.%I USING BRIN (je_date);', part_name, part_name);
  END IF;

  RETURN part_name;
END; $$;

-- Monthly balance snapshot
DROP TABLE IF EXISTS public.account_balance_snapshot;
CREATE TABLE public.account_balance_snapshot (
  period_start   date NOT NULL,
  account_code   varchar(50) NOT NULL,
  fund           varchar(10) NOT NULL,
  opening_balance numeric(20,6) NOT NULL DEFAULT 0,
  debit           numeric(20,6) NOT NULL DEFAULT 0,
  credit          numeric(20,6) NOT NULL DEFAULT 0,
  closing_balance numeric(20,6) NOT NULL DEFAULT 0,
  calculated_at   timestamp DEFAULT now(),
  CONSTRAINT acc_bal_snapshot_pk PRIMARY KEY (period_start, account_code, fund)
);
CREATE INDEX IF NOT EXISTS idx_abs_period ON public.account_balance_snapshot(period_start);

```

### Reporting convenience

```sql
-- Trial balance for a month, computed from ledger (can be a MV if desired)
CREATE OR REPLACE VIEW public.v_trial_balance_month AS
SELECT
  date_trunc('month', h.je_date)::date AS period_start,
  l.account_code,
  l.fund,
  SUM(CASE WHEN l.side='DR' THEN l.amount ELSE 0 END) AS debit,
  SUM(CASE WHEN l.side='CR' THEN l.amount ELSE 0 END) AS credit,
  SUM(CASE WHEN l.side='DR' THEN l.amount ELSE 0 END) -
  SUM(CASE WHEN l.side='CR' THEN l.amount ELSE 0 END) AS net
FROM public.ledger_entry_line l
JOIN public.ledger_entry_header h ON h.je_id = l.je_id
GROUP BY 1,2,3;

```
