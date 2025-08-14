-- Table Partitioning Strategy for High-Performance Journal Processing
-- Partition by month for optimal query performance

-- ========================================
-- 1. CREATE NEW PARTITIONED TABLE STRUCTURE
-- ========================================

-- Create partitioned version of sun_journal
CREATE TABLE IF NOT EXISTS sun_journal_partitioned (
    id VARCHAR(32) NOT NULL,
    source_rowid VARCHAR(32),
    voucher_id VARCHAR(32),
    data JSONB,
    journal_type VARCHAR(5),
    journal_date DATE NOT NULL,
    created_date TIMESTAMP DEFAULT NOW(),
    created_by INTEGER,
    search_id VARCHAR[],
    PRIMARY KEY (id, journal_date)
) PARTITION BY RANGE (journal_date);

-- Create partitioned version of gl_entries
CREATE TABLE IF NOT EXISTS gl_entries_partitioned (
    id SERIAL,
    trx_id VARCHAR(100),
    acc_debit VARCHAR(50),
    acc_credit VARCHAR(50),
    amount NUMERIC(20,2),
    trx_date DATE NOT NULL,
    t_1 VARCHAR(20),
    t_2 VARCHAR(20),
    t_3 VARCHAR(20),
    t_4 VARCHAR(20),
    t_5 VARCHAR(20),
    t_6 VARCHAR(20),
    t_7 VARCHAR(20),
    t_8 VARCHAR(20),
    t_9 VARCHAR(20),
    t_10 VARCHAR(20),
    data JSON,
    created_date TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (id, trx_date)
) PARTITION BY RANGE (trx_date);

-- ========================================
-- 2. CREATE PARTITION MANAGEMENT FUNCTION
-- ========================================

CREATE OR REPLACE FUNCTION create_monthly_partitions(
    table_name TEXT,
    start_date DATE,
    end_date DATE
) RETURNS VOID AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_range DATE;
    end_range DATE;
BEGIN
    partition_date := DATE_TRUNC('month', start_date);
    
    WHILE partition_date < end_date LOOP
        partition_name := table_name || '_' || TO_CHAR(partition_date, 'YYYY_MM');
        start_range := partition_date;
        end_range := partition_date + INTERVAL '1 month';
        
        -- Check if partition exists
        IF NOT EXISTS (
            SELECT 1 FROM pg_class 
            WHERE relname = partition_name
        ) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                partition_name,
                table_name,
                start_range,
                end_range
            );
            
            RAISE NOTICE 'Created partition: %', partition_name;
        END IF;
        
        partition_date := partition_date + INTERVAL '1 month';
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 3. CREATE PARTITIONS FOR HISTORICAL DATA
-- ========================================

-- Create partitions from 2019 to 2025
SELECT create_monthly_partitions('sun_journal_partitioned', '2019-01-01'::DATE, '2025-12-31'::DATE);
SELECT create_monthly_partitions('gl_entries_partitioned', '2019-01-01'::DATE, '2025-12-31'::DATE);

-- ========================================
-- 4. AUTOMATED PARTITION MAINTENANCE
-- ========================================

-- Function to automatically create future partitions
CREATE OR REPLACE FUNCTION auto_create_partitions() RETURNS VOID AS $$
DECLARE
    next_month DATE;
    three_months_ahead DATE;
BEGIN
    next_month := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month');
    three_months_ahead := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '3 months');
    
    -- Create partitions 3 months ahead
    PERFORM create_monthly_partitions('sun_journal_partitioned', next_month, three_months_ahead);
    PERFORM create_monthly_partitions('gl_entries_partitioned', next_month, three_months_ahead);
END;
$$ LANGUAGE plpgsql;

-- Schedule monthly job to create partitions (using pg_cron if available)
-- CREATE EXTENSION IF NOT EXISTS pg_cron;
-- SELECT cron.schedule('create-partitions', '0 0 1 * *', 'SELECT auto_create_partitions();');

-- ========================================
-- 5. MIGRATE DATA TO PARTITIONED TABLES
-- ========================================

-- Migration function with progress tracking
CREATE OR REPLACE FUNCTION migrate_to_partitioned_tables(
    batch_size INTEGER DEFAULT 10000
) RETURNS TABLE(table_name TEXT, rows_migrated BIGINT, duration INTERVAL) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    total_rows BIGINT;
    migrated_rows BIGINT := 0;
BEGIN
    -- Migrate sun_journal
    start_time := CLOCK_TIMESTAMP();
    
    INSERT INTO sun_journal_partitioned
    SELECT * FROM sun_journal
    WHERE journal_date >= '2019-01-01'
    ON CONFLICT (id, journal_date) DO NOTHING;
    
    GET DIAGNOSTICS migrated_rows = ROW_COUNT;
    end_time := CLOCK_TIMESTAMP();
    
    RETURN QUERY SELECT 'sun_journal'::TEXT, migrated_rows, end_time - start_time;
    
    -- Migrate gl_entries
    start_time := CLOCK_TIMESTAMP();
    migrated_rows := 0;
    
    INSERT INTO gl_entries_partitioned (
        trx_id, acc_debit, acc_credit, amount, trx_date,
        t_1, t_2, t_3, t_4, t_5, t_6, t_7, t_8, t_9, t_10, data
    )
    SELECT 
        trx_id, acc_debit, acc_credit, amount, trx_date,
        t_1, t_2, t_3, t_4, t_5, t_6, t_7, t_8, t_9, t_10, data
    FROM gl_entries
    WHERE trx_date >= '2019-01-01'
    ON CONFLICT DO NOTHING;
    
    GET DIAGNOSTICS migrated_rows = ROW_COUNT;
    end_time := CLOCK_TIMESTAMP();
    
    RETURN QUERY SELECT 'gl_entries'::TEXT, migrated_rows, end_time - start_time;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 6. CREATE INDEXES ON PARTITIONED TABLES
-- ========================================

-- Indexes on sun_journal_partitioned
CREATE INDEX idx_sun_journal_part_data_gin 
ON sun_journal_partitioned USING GIN (data);

CREATE INDEX idx_sun_journal_part_type 
ON sun_journal_partitioned (journal_type);

CREATE INDEX idx_sun_journal_part_unvouchered 
ON sun_journal_partitioned (journal_type) 
WHERE voucher_id IS NULL;

CREATE INDEX idx_sun_journal_part_search_id 
ON sun_journal_partitioned USING GIN (search_id);

-- Indexes on gl_entries_partitioned
CREATE INDEX idx_gl_entries_part_accounts 
ON gl_entries_partitioned (acc_debit, acc_credit);

CREATE INDEX idx_gl_entries_part_t_codes 
ON gl_entries_partitioned (t_1, t_2, t_3, t_4, t_5);

-- ========================================
-- 7. PARTITION PRUNING CONFIGURATION
-- ========================================

-- Enable partition pruning
SET enable_partition_pruning = on;
SET constraint_exclusion = partition;

-- ========================================
-- 8. VIEWS FOR BACKWARD COMPATIBILITY
-- ========================================

-- Create views with original names pointing to partitioned tables
CREATE OR REPLACE VIEW sun_journal_v AS
SELECT * FROM sun_journal_partitioned;

CREATE OR REPLACE VIEW gl_entries_v AS
SELECT * FROM gl_entries_partitioned;

-- ========================================
-- 9. PARTITION MAINTENANCE QUERIES
-- ========================================

-- View to monitor partition sizes
CREATE OR REPLACE VIEW v_partition_sizes AS
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
FROM pg_tables
WHERE tablename LIKE '%_2%'
  AND (tablename LIKE 'sun_journal_%' OR tablename LIKE 'gl_entries_%')
ORDER BY tablename;

-- Function to drop old partitions
CREATE OR REPLACE FUNCTION drop_old_partitions(
    table_name TEXT,
    retention_months INTEGER DEFAULT 36
) RETURNS VOID AS $$
DECLARE
    cutoff_date DATE;
    partition_name TEXT;
    partition_rec RECORD;
BEGIN
    cutoff_date := DATE_TRUNC('month', CURRENT_DATE - (retention_months || ' months')::INTERVAL);
    
    FOR partition_rec IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE tablename LIKE table_name || '_%'
          AND tablename ~ '\d{4}_\d{2}$'
    LOOP
        -- Extract date from partition name
        IF TO_DATE(RIGHT(partition_rec.tablename, 7), 'YYYY_MM') < cutoff_date THEN
            EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', partition_rec.tablename);
            RAISE NOTICE 'Dropped old partition: %', partition_rec.tablename;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;