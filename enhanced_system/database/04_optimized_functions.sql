-- Optimized PostgreSQL Functions for Enhanced Performance
-- Using set-based operations, bulk inserts, and parallel processing

-- ========================================
-- 1. OPTIMIZED JOURNAL INSERTION FUNCTION
-- ========================================

CREATE OR REPLACE FUNCTION fn_insert_sun_journal_optimized(
    p_journal_date DATE,
    p_created_by INTEGER
) RETURNS TABLE(
    status_code INTEGER,
    journals_created INTEGER,
    vouchers_created INTEGER,
    execution_time_ms NUMERIC
) AS $$
DECLARE
    v_start_time TIMESTAMP;
    v_journal_count INTEGER := 0;
    v_voucher_count INTEGER := 0;
    v_start_journal_process DATE := '2019-05-01';
BEGIN
    v_start_time := CLOCK_TIMESTAMP();
    
    -- Early exit for dates before cutoff
    IF p_journal_date < v_start_journal_process THEN
        RETURN QUERY SELECT 
            1::INTEGER, 
            0::INTEGER, 
            0::INTEGER, 
            0::NUMERIC;
        RETURN;
    END IF;
    
    -- Use CTE for better performance and readability
    WITH active_settings AS (
        -- Get active journal settings with better filtering
        SELECT 
            journal_type,
            journal_set,
            (journal_set->>'ds')::INTEGER as datasource_id
        FROM sun_journal_setting
        WHERE status = 1
          AND (
              (journal_set->'start_period' IS NULL AND journal_set->'end_period' IS NULL)
              OR (
                  journal_set->'start_period' IS NOT NULL 
                  AND journal_set->'end_period' IS NOT NULL
                  AND p_journal_date BETWEEN (journal_set->>'start_period')::DATE 
                                          AND (journal_set->>'end_period')::DATE
              )
              OR (
                  journal_set->'end_period' IS NOT NULL 
                  AND status2 = 1 
                  AND p_journal_date > (journal_set->>'end_period')::DATE
              )
          )
    ),
    
    -- Process journals in bulk
    journal_inserts AS (
        INSERT INTO sun_journal (id, source_rowid, data, journal_type, journal_date, created_by, search_id)
        SELECT 
            uuid_generate_v4()::VARCHAR,
            ds.id,
            jsonb_build_object(
                'journal', array_to_json(journal_lines),
                'journal_date', p_journal_date,
                'journal_type', s.journal_type
            ),
            s.journal_type,
            p_journal_date,
            p_created_by,
            ARRAY[ds.general_description_3]
        FROM active_settings s
        CROSS JOIN LATERAL fn_get_datasource_sun_journal(
            p_journal_date, 
            s.datasource_id, 
            p_journal_date, 
            p_journal_date
        ) ds
        CROSS JOIN LATERAL (
            SELECT array_agg(
                fn_build_journal_line(s.journal_type, ds.*, r.*)
            ) as journal_lines
            FROM fn_get_row_record_sun_journal_setting(s.journal_type, ds.id) r
            WHERE fn_get_transaction_amount(r, ds) > 0
        ) lines
        WHERE journal_lines IS NOT NULL
        ON CONFLICT (source_rowid, journal_type) DO NOTHING
        RETURNING 1
    )
    SELECT COUNT(*) INTO v_journal_count FROM journal_inserts;
    
    -- Process GL entries in bulk
    PERFORM fn_process_gl_entries_bulk(p_journal_date);
    
    -- Create vouchers
    v_voucher_count := fn_insert_sun_voucher_optimized(p_journal_date);
    
    -- Return results
    RETURN QUERY SELECT 
        0::INTEGER as status_code,
        v_journal_count,
        v_voucher_count,
        EXTRACT(MILLISECONDS FROM (CLOCK_TIMESTAMP() - v_start_time))::NUMERIC as execution_time_ms;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 2. OPTIMIZED VOUCHER CREATION
-- ========================================

CREATE OR REPLACE FUNCTION fn_insert_sun_voucher_optimized(
    p_journal_date DATE
) RETURNS INTEGER AS $$
DECLARE
    v_voucher_count INTEGER := 0;
BEGIN
    -- Use UPSERT for better concurrency handling
    WITH voucher_data AS (
        SELECT 
            uuid_generate_v4()::VARCHAR as voucher_id,
            journal_type,
            p_journal_date as journal_date,
            journal_type || TO_CHAR(p_journal_date, 'YYMMDD') || 
                LPAD(ROW_NUMBER() OVER (PARTITION BY journal_type ORDER BY grouping_key)::TEXT, 4, '0') as voucher_no,
            jsonb_build_object(
                'journal', jsonb_agg(journal_line ORDER BY line_number)
            ) as data,
            array_agg(journal_id) as journal_ids
        FROM (
            SELECT 
                j.id as journal_id,
                j.journal_type,
                jsonb_array_elements(j.data->'journal') as journal_line,
                (jsonb_array_elements(j.data->'journal')->'baris'->3)::INTEGER as line_number,
                -- Create grouping key for voucher consolidation
                MD5(
                    j.journal_type || '|' ||
                    (jsonb_array_elements(j.data->'journal')->'baris'->1)::TEXT || '|' ||
                    (jsonb_array_elements(j.data->'journal')->'baris'->2)::TEXT || '|' ||
                    (jsonb_array_elements(j.data->'journal')->'baris'->5)::TEXT
                ) as grouping_key
            FROM sun_journal j
            WHERE j.journal_date = p_journal_date
              AND j.voucher_id IS NULL
        ) journal_lines
        GROUP BY journal_type, grouping_key
    ),
    inserted_vouchers AS (
        INSERT INTO sun_voucher (id, journal_type, journal_date, voucher_no, data)
        SELECT voucher_id, journal_type, journal_date, voucher_no, data
        FROM voucher_data
        RETURNING id, journal_type
    ),
    updated_journals AS (
        UPDATE sun_journal j
        SET voucher_id = v.voucher_id
        FROM (
            SELECT unnest(vd.journal_ids) as journal_id, vd.voucher_id
            FROM voucher_data vd
            JOIN inserted_vouchers iv ON iv.id = vd.voucher_id
        ) v
        WHERE j.id = v.journal_id
        RETURNING 1
    )
    SELECT COUNT(*) INTO v_voucher_count FROM inserted_vouchers;
    
    RETURN v_voucher_count;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 3. BULK GL ENTRIES PROCESSING
-- ========================================

CREATE OR REPLACE FUNCTION fn_process_gl_entries_bulk(
    p_journal_date DATE
) RETURNS VOID AS $$
BEGIN
    -- Bulk insert GL entries with better performance
    INSERT INTO gl_entries (
        trx_id, acc_debit, acc_credit, amount, trx_date,
        t_1, t_2, t_3, t_4, t_5, t_6, t_7, t_8, t_9, t_10, data
    )
    SELECT 
        j.data->>'transaction_reference',
        CASE WHEN l.d_c_marker = 'D' THEN l.account_code END,
        CASE WHEN l.d_c_marker = 'C' THEN l.account_code END,
        l.amount,
        p_journal_date,
        l.t_1, l.t_2, l.t_3, l.t_4, l.t_5, 
        l.t_6, l.t_7, l.t_8, l.t_9, l.t_10,
        jsonb_build_object(
            'journal_id', j.id,
            'journal_type', j.journal_type,
            'line_number', l.line_number
        )
    FROM sun_journal j
    CROSS JOIN LATERAL (
        SELECT 
            (line->>'line_number')::INTEGER as line_number,
            line->>'account_code' as account_code,
            (line->>'amount')::NUMERIC as amount,
            line->>'d_c_marker' as d_c_marker,
            line->>'t_1' as t_1,
            line->>'t_2' as t_2,
            line->>'t_3' as t_3,
            line->>'t_4' as t_4,
            line->>'t_5' as t_5,
            line->>'t_6' as t_6,
            line->>'t_7' as t_7,
            line->>'t_8' as t_8,
            line->>'t_9' as t_9,
            line->>'t_10' as t_10
        FROM jsonb_array_elements(j.data->'journal') as line
        WHERE (line->>'account_flag')::INTEGER IN (1, 3, 4)
    ) l
    WHERE j.journal_date = p_journal_date
    ON CONFLICT DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 4. PARALLEL PROCESSING WRAPPER
-- ========================================

CREATE OR REPLACE FUNCTION fn_process_journal_date_parallel(
    p_journal_date DATE,
    p_created_by INTEGER,
    p_parallel_workers INTEGER DEFAULT 4
) RETURNS TABLE(
    status_code INTEGER,
    total_journals INTEGER,
    total_vouchers INTEGER,
    total_time_ms NUMERIC
) AS $$
DECLARE
    v_start_time TIMESTAMP;
    v_total_journals INTEGER := 0;
    v_total_vouchers INTEGER := 0;
BEGIN
    v_start_time := CLOCK_TIMESTAMP();
    
    -- Set parallel workers for this session
    EXECUTE format('SET LOCAL max_parallel_workers_per_gather = %s', p_parallel_workers);
    EXECUTE 'SET LOCAL parallel_setup_cost = 0';
    EXECUTE 'SET LOCAL parallel_tuple_cost = 0';
    
    -- Process with parallel execution
    WITH parallel_process AS (
        SELECT * FROM fn_insert_sun_journal_optimized(p_journal_date, p_created_by)
    )
    SELECT 
        status_code,
        journals_created,
        vouchers_created
    INTO 
        status_code,
        v_total_journals,
        v_total_vouchers
    FROM parallel_process;
    
    -- Return aggregated results
    RETURN QUERY SELECT 
        0::INTEGER,
        v_total_journals,
        v_total_vouchers,
        EXTRACT(MILLISECONDS FROM (CLOCK_TIMESTAMP() - v_start_time))::NUMERIC;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 5. BATCH PROCESSING FOR MULTIPLE DATES
-- ========================================

CREATE OR REPLACE FUNCTION fn_process_journal_batch(
    p_start_date DATE,
    p_end_date DATE,
    p_created_by INTEGER,
    p_batch_size INTEGER DEFAULT 7  -- Process 7 days at a time
) RETURNS TABLE(
    batch_date DATE,
    journals_created INTEGER,
    vouchers_created INTEGER,
    execution_time_ms NUMERIC,
    success BOOLEAN,
    error_message TEXT
) AS $$
DECLARE
    v_current_date DATE;
    v_batch_end DATE;
    v_result RECORD;
BEGIN
    v_current_date := p_start_date;
    
    WHILE v_current_date <= p_end_date LOOP
        v_batch_end := LEAST(v_current_date + (p_batch_size - 1), p_end_date);
        
        -- Process each date in the batch
        FOR v_result IN 
            SELECT 
                d::DATE as process_date
            FROM generate_series(v_current_date, v_batch_end, '1 day'::INTERVAL) d
        LOOP
            BEGIN
                -- Process single date
                RETURN QUERY
                SELECT 
                    v_result.process_date,
                    r.journals_created,
                    r.vouchers_created,
                    r.execution_time_ms,
                    TRUE::BOOLEAN as success,
                    NULL::TEXT as error_message
                FROM fn_insert_sun_journal_optimized(v_result.process_date, p_created_by) r;
                
            EXCEPTION WHEN OTHERS THEN
                -- Log error and continue
                RETURN QUERY
                SELECT 
                    v_result.process_date,
                    0::INTEGER,
                    0::INTEGER,
                    0::NUMERIC,
                    FALSE::BOOLEAN as success,
                    SQLERRM::TEXT as error_message;
            END;
        END LOOP;
        
        v_current_date := v_batch_end + INTERVAL '1 day';
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 6. MONITORING AND METRICS FUNCTIONS
-- ========================================

CREATE OR REPLACE FUNCTION fn_get_processing_metrics(
    p_date DATE DEFAULT CURRENT_DATE
) RETURNS TABLE(
    metric_name TEXT,
    metric_value NUMERIC,
    metric_unit TEXT
) AS $$
BEGIN
    RETURN QUERY
    -- Processing time metrics
    SELECT 
        'avg_processing_time'::TEXT,
        AVG(EXTRACT(EPOCH FROM (created_date - journal_date::TIMESTAMP)))::NUMERIC,
        'seconds'::TEXT
    FROM sun_journal
    WHERE journal_date = p_date
    
    UNION ALL
    
    -- Journal count metrics
    SELECT 
        'total_journals'::TEXT,
        COUNT(*)::NUMERIC,
        'count'::TEXT
    FROM sun_journal
    WHERE journal_date = p_date
    
    UNION ALL
    
    -- Voucher count metrics
    SELECT 
        'total_vouchers'::TEXT,
        COUNT(*)::NUMERIC,
        'count'::TEXT
    FROM sun_voucher
    WHERE journal_date = p_date
    
    UNION ALL
    
    -- GL entries metrics
    SELECT 
        'total_gl_entries'::TEXT,
        COUNT(*)::NUMERIC,
        'count'::TEXT
    FROM gl_entries
    WHERE trx_date = p_date
    
    UNION ALL
    
    -- Data volume metrics
    SELECT 
        'total_data_size'::TEXT,
        SUM(pg_column_size(data))::NUMERIC / 1024 / 1024,
        'MB'::TEXT
    FROM sun_journal
    WHERE journal_date = p_date;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 7. CLEANUP AND MAINTENANCE FUNCTIONS
-- ========================================

CREATE OR REPLACE FUNCTION fn_cleanup_old_journals(
    p_retention_days INTEGER DEFAULT 1095  -- 3 years
) RETURNS TABLE(
    table_name TEXT,
    rows_deleted BIGINT
) AS $$
DECLARE
    v_cutoff_date DATE;
BEGIN
    v_cutoff_date := CURRENT_DATE - p_retention_days;
    
    -- Delete old test data
    DELETE FROM test_table
    WHERE created_date < v_cutoff_date;
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN QUERY SELECT 'test_table'::TEXT, rows_deleted;
    
    -- Archive old journals (move to archive table instead of deleting)
    -- This is safer for audit requirements
    INSERT INTO sun_journal_archive
    SELECT * FROM sun_journal
    WHERE journal_date < v_cutoff_date
    ON CONFLICT DO NOTHING;
    
    DELETE FROM sun_journal
    WHERE journal_date < v_cutoff_date;
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN QUERY SELECT 'sun_journal'::TEXT, rows_deleted;
END;
$$ LANGUAGE plpgsql;