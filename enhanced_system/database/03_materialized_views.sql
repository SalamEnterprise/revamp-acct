-- Materialized Views for Fast Reporting and Analytics
-- Refresh strategy: Daily for historical, hourly for current month

-- ========================================
-- 1. JOURNAL SUMMARY BY DATE AND TYPE
-- ========================================

DROP MATERIALIZED VIEW IF EXISTS mv_journal_daily_summary CASCADE;
CREATE MATERIALIZED VIEW mv_journal_daily_summary AS
SELECT 
    journal_date,
    journal_type,
    COUNT(*) as entry_count,
    COUNT(DISTINCT source_rowid) as unique_sources,
    COUNT(CASE WHEN voucher_id IS NULL THEN 1 END) as unvouchered_count,
    COUNT(CASE WHEN voucher_id IS NOT NULL THEN 1 END) as vouchered_count,
    SUM((data->'transaction_amount'->>'amount')::NUMERIC) as total_amount,
    AVG((data->'transaction_amount'->>'amount')::NUMERIC) as avg_amount,
    MIN(created_date) as first_created,
    MAX(created_date) as last_created,
    ARRAY_AGG(DISTINCT data->>'status') as statuses
FROM sun_journal
WHERE journal_date >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL '2 years')
GROUP BY journal_date, journal_type
WITH DATA;

CREATE UNIQUE INDEX idx_mv_journal_daily_summary 
ON mv_journal_daily_summary (journal_date, journal_type);

-- ========================================
-- 2. ACCOUNT BALANCE SUMMARY
-- ========================================

DROP MATERIALIZED VIEW IF EXISTS mv_account_balance CASCADE;
CREATE MATERIALIZED VIEW mv_account_balance AS
SELECT 
    trx_date,
    acc_debit,
    acc_credit,
    COUNT(*) as transaction_count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount,
    MIN(amount) as min_amount,
    MAX(amount) as max_amount,
    STRING_AGG(DISTINCT t_1, ',') as t1_codes,
    STRING_AGG(DISTINCT t_2, ',') as t2_codes,
    STRING_AGG(DISTINCT t_3, ',') as t3_codes
FROM gl_entries
WHERE trx_date >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')
GROUP BY trx_date, acc_debit, acc_credit
WITH DATA;

CREATE UNIQUE INDEX idx_mv_account_balance 
ON mv_account_balance (trx_date, acc_debit, acc_credit);

-- ========================================
-- 3. VOUCHER SUMMARY
-- ========================================

DROP MATERIALIZED VIEW IF EXISTS mv_voucher_summary CASCADE;
CREATE MATERIALIZED VIEW mv_voucher_summary AS
SELECT 
    journal_date,
    journal_type,
    COUNT(*) as voucher_count,
    COUNT(DISTINCT voucher_no) as unique_vouchers,
    MIN(voucher_no) as first_voucher,
    MAX(voucher_no) as last_voucher,
    SUM(jsonb_array_length(data->'journal')) as total_lines,
    AVG(jsonb_array_length(data->'journal')) as avg_lines_per_voucher
FROM sun_voucher
WHERE journal_date >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')
GROUP BY journal_date, journal_type
WITH DATA;

CREATE UNIQUE INDEX idx_mv_voucher_summary 
ON mv_voucher_summary (journal_date, journal_type);

-- ========================================
-- 4. TRANSACTION CODE ANALYSIS
-- ========================================

DROP MATERIALIZED VIEW IF EXISTS mv_tcode_analysis CASCADE;
CREATE MATERIALIZED VIEW mv_tcode_analysis AS
WITH tcode_data AS (
    SELECT 
        trx_date,
        t_1, t_2, t_3, t_4, t_5,
        amount,
        acc_debit,
        acc_credit
    FROM gl_entries
    WHERE trx_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '6 months')
)
SELECT 
    DATE_TRUNC('month', trx_date) as month,
    t_1 as t_code_1,
    t_2 as t_code_2,
    t_3 as t_code_3,
    COUNT(*) as transaction_count,
    SUM(amount) as total_amount,
    COUNT(DISTINCT acc_debit) as unique_debit_accounts,
    COUNT(DISTINCT acc_credit) as unique_credit_accounts,
    AVG(amount) as avg_transaction_amount,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) as median_amount
FROM tcode_data
GROUP BY DATE_TRUNC('month', trx_date), t_1, t_2, t_3
WITH DATA;

CREATE INDEX idx_mv_tcode_analysis 
ON mv_tcode_analysis (month, t_code_1, t_code_2, t_code_3);

-- ========================================
-- 5. PROCESSING PERFORMANCE METRICS
-- ========================================

DROP MATERIALIZED VIEW IF EXISTS mv_processing_metrics CASCADE;
CREATE MATERIALIZED VIEW mv_processing_metrics AS
SELECT 
    DATE_TRUNC('hour', created_date) as hour,
    journal_type,
    COUNT(*) as records_processed,
    AVG(EXTRACT(EPOCH FROM (created_date - journal_date::timestamp))) as avg_processing_delay_seconds,
    MIN(created_date) as first_processed,
    MAX(created_date) as last_processed,
    MAX(created_date) - MIN(created_date) as processing_duration
FROM sun_journal
WHERE created_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', created_date), journal_type
WITH DATA;

CREATE INDEX idx_mv_processing_metrics 
ON mv_processing_metrics (hour, journal_type);

-- ========================================
-- 6. DATA QUALITY METRICS
-- ========================================

DROP MATERIALIZED VIEW IF EXISTS mv_data_quality CASCADE;
CREATE MATERIALIZED VIEW mv_data_quality AS
SELECT 
    journal_date,
    journal_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN data IS NULL THEN 1 END) as null_data_count,
    COUNT(CASE WHEN search_id IS NULL THEN 1 END) as null_search_id_count,
    COUNT(CASE WHEN voucher_id IS NULL AND journal_date < CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as old_unvouchered,
    COUNT(CASE WHEN jsonb_typeof(data) != 'object' THEN 1 END) as invalid_json_count,
    COUNT(CASE WHEN data->>'journal_type' != journal_type THEN 1 END) as type_mismatch_count
FROM sun_journal
WHERE journal_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '3 months')
GROUP BY journal_date, journal_type
WITH DATA;

CREATE UNIQUE INDEX idx_mv_data_quality 
ON mv_data_quality (journal_date, journal_type);

-- ========================================
-- 7. REFRESH FUNCTIONS
-- ========================================

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_all_materialized_views() 
RETURNS TABLE(view_name TEXT, refresh_time INTERVAL) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    mv_record RECORD;
BEGIN
    FOR mv_record IN 
        SELECT matviewname 
        FROM pg_matviews 
        WHERE schemaname = 'public' 
          AND matviewname LIKE 'mv_%'
        ORDER BY matviewname
    LOOP
        start_time := CLOCK_TIMESTAMP();
        EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I', mv_record.matviewname);
        end_time := CLOCK_TIMESTAMP();
        
        RETURN QUERY SELECT mv_record.matviewname::TEXT, end_time - start_time;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh specific materialized view with logging
CREATE OR REPLACE FUNCTION refresh_materialized_view_with_log(
    view_name TEXT
) RETURNS VOID AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    row_count BIGINT;
BEGIN
    start_time := CLOCK_TIMESTAMP();
    
    EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I', view_name);
    
    end_time := CLOCK_TIMESTAMP();
    
    -- Log the refresh
    INSERT INTO IF NOT EXISTS materialized_view_refresh_log (
        view_name,
        refresh_start,
        refresh_end,
        duration,
        success
    ) VALUES (
        view_name,
        start_time,
        end_time,
        end_time - start_time,
        TRUE
    );
    
    RAISE NOTICE 'Refreshed % in %', view_name, end_time - start_time;
EXCEPTION
    WHEN OTHERS THEN
        -- Log the error
        INSERT INTO IF NOT EXISTS materialized_view_refresh_log (
            view_name,
            refresh_start,
            refresh_end,
            duration,
            success,
            error_message
        ) VALUES (
            view_name,
            start_time,
            CLOCK_TIMESTAMP(),
            CLOCK_TIMESTAMP() - start_time,
            FALSE,
            SQLERRM
        );
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 8. REFRESH SCHEDULE (using pg_cron if available)
-- ========================================

-- Create log table for refresh history
CREATE TABLE IF NOT EXISTS materialized_view_refresh_log (
    id SERIAL PRIMARY KEY,
    view_name TEXT NOT NULL,
    refresh_start TIMESTAMP NOT NULL,
    refresh_end TIMESTAMP NOT NULL,
    duration INTERVAL,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedule refresh jobs (uncomment if pg_cron is installed)
-- Daily refresh for historical views
-- SELECT cron.schedule('refresh-daily-summary', '0 1 * * *', 
--     'SELECT refresh_materialized_view_with_log(''mv_journal_daily_summary'');');
-- 
-- SELECT cron.schedule('refresh-account-balance', '30 1 * * *', 
--     'SELECT refresh_materialized_view_with_log(''mv_account_balance'');');
-- 
-- -- Hourly refresh for current metrics
-- SELECT cron.schedule('refresh-processing-metrics', '5 * * * *', 
--     'SELECT refresh_materialized_view_with_log(''mv_processing_metrics'');');
-- 
-- SELECT cron.schedule('refresh-data-quality', '10 * * * *', 
--     'SELECT refresh_materialized_view_with_log(''mv_data_quality'');');

-- ========================================
-- 9. QUERY EXAMPLES USING MATERIALIZED VIEWS
-- ========================================

-- Example: Get daily processing summary
-- SELECT * FROM mv_journal_daily_summary 
-- WHERE journal_date >= CURRENT_DATE - INTERVAL '30 days'
-- ORDER BY journal_date DESC, journal_type;

-- Example: Get account activity
-- SELECT * FROM mv_account_balance
-- WHERE trx_date = CURRENT_DATE
-- ORDER BY total_amount DESC
-- LIMIT 20;

-- Example: Monitor data quality
-- SELECT * FROM mv_data_quality
-- WHERE journal_date >= CURRENT_DATE - INTERVAL '7 days'
--   AND (null_data_count > 0 OR old_unvouchered > 0)
-- ORDER BY journal_date DESC;