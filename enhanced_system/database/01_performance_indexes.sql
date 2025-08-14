-- Performance Optimization Indexes for Journal System
-- Expected Performance Improvement: 5-10x

-- ========================================
-- 1. OPTIMIZED INDEXES FOR sun_journal
-- ========================================

-- GIN index for JSONB queries (if not exists)
DROP INDEX IF EXISTS idx_sun_journal_data_gin;
CREATE INDEX CONCURRENTLY idx_sun_journal_data_gin 
ON sun_journal USING GIN (data);

-- Composite index for date and type queries
DROP INDEX IF EXISTS idx_sun_journal_date_type;
CREATE INDEX CONCURRENTLY idx_sun_journal_date_type 
ON sun_journal (journal_date, journal_type);

-- Partial index for unvouchered journals
DROP INDEX IF EXISTS idx_sun_journal_unvouchered;
CREATE INDEX CONCURRENTLY idx_sun_journal_unvouchered 
ON sun_journal (journal_date, journal_type) 
WHERE voucher_id IS NULL;

-- Index for search_id array
DROP INDEX IF EXISTS idx_sun_journal_search_id;
CREATE INDEX CONCURRENTLY idx_sun_journal_search_id 
ON sun_journal USING GIN (search_id);

-- Expression index for frequently accessed JSON paths
DROP INDEX IF EXISTS idx_sun_journal_amount;
CREATE INDEX CONCURRENTLY idx_sun_journal_amount 
ON sun_journal (((data->'transaction_amount')::numeric));

-- Index for journal status
DROP INDEX IF EXISTS idx_sun_journal_status;
CREATE INDEX CONCURRENTLY idx_sun_journal_status 
ON sun_journal ((data->>'status')) 
WHERE data->>'status' IS NOT NULL;

-- ========================================
-- 2. OPTIMIZED INDEXES FOR gl_entries
-- ========================================

DROP INDEX IF EXISTS idx_gl_entries_trx_date;
CREATE INDEX CONCURRENTLY idx_gl_entries_trx_date 
ON gl_entries (trx_date);

DROP INDEX IF EXISTS idx_gl_entries_accounts;
CREATE INDEX CONCURRENTLY idx_gl_entries_accounts 
ON gl_entries (acc_debit, acc_credit);

DROP INDEX IF EXISTS idx_gl_entries_t_codes;
CREATE INDEX CONCURRENTLY idx_gl_entries_t_codes 
ON gl_entries (t_1, t_2, t_3, t_4, t_5);

-- Composite index for common queries
DROP INDEX IF EXISTS idx_gl_entries_date_accounts;
CREATE INDEX CONCURRENTLY idx_gl_entries_date_accounts 
ON gl_entries (trx_date, acc_debit, acc_credit);

-- ========================================
-- 3. OPTIMIZED INDEXES FOR sun_voucher
-- ========================================

DROP INDEX IF EXISTS idx_sun_voucher_date_type;
CREATE INDEX CONCURRENTLY idx_sun_voucher_date_type 
ON sun_voucher (journal_date, journal_type);

DROP INDEX IF EXISTS idx_sun_voucher_no;
CREATE INDEX CONCURRENTLY idx_sun_voucher_no 
ON sun_voucher (voucher_no);

-- ========================================
-- 4. OPTIMIZED INDEXES FOR sun_journal_setting
-- ========================================

-- Partial index for active settings
DROP INDEX IF EXISTS idx_sun_journal_setting_active;
CREATE INDEX CONCURRENTLY idx_sun_journal_setting_active 
ON sun_journal_setting (journal_type) 
WHERE status = 1;

-- GIN index for journal_set JSONB
DROP INDEX IF EXISTS idx_sun_journal_setting_jsonb;
CREATE INDEX CONCURRENTLY idx_sun_journal_setting_jsonb 
ON sun_journal_setting USING GIN (journal_set);

-- ========================================
-- 5. STATISTICS UPDATE
-- ========================================

-- Update statistics for better query planning
ANALYZE sun_journal;
ANALYZE gl_entries;
ANALYZE sun_voucher;
ANALYZE sun_journal_setting;

-- ========================================
-- 6. QUERY PERFORMANCE MONITORING
-- ========================================

-- Enable query statistics if not already enabled
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View to monitor slow queries
CREATE OR REPLACE VIEW v_slow_queries AS
SELECT 
    query,
    calls,
    mean_exec_time,
    total_exec_time,
    min_exec_time,
    max_exec_time,
    stddev_exec_time
FROM pg_stat_statements
WHERE query LIKE '%sun_journal%' 
   OR query LIKE '%gl_entries%'
   OR query LIKE '%fn_insert%'
ORDER BY mean_exec_time DESC
LIMIT 20;