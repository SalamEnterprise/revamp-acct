### Database Schema
```sql
  -- Quick reference of key tables

-- Source Tables (Read)
premium_transaction (txn_id, premium_amount, fund_tabarru, fund_tanahud, fund_ujroh)
claims_transaction (claim_id, claim_amount, fund allocations)

-- Staging Tables (Temp)
staging_month_end_master (batch_id, status, sequence ranges)
staging_je_header (staging_header_id, je_number, je_sequence)
staging_je_line (staging_line_id, account_code, amounts)

-- Production Tables (Write)
journal_entry_header (je_id, je_number, amounts, batch_id)
journal_entry_line (line_id, je_id, account_code, amounts)
fund_balance (fund_type, current_balance)

-- Control Tables
batch_worker_control (worker_id, batch_id, status, progress)
batch_processing_checkpoint (checkpoint_id, worker_id, progress)
batch_validation_results (validation_id, batch_id, results)

-- Audit Tables
audit_batch_operations (audit_id, batch_id, operation, user)
sequence_reservation_log (reservation_id, start_seq, end_seq)
  ```
  
### API Quick Reference
```api
# Quick API Reference

# Initiate Batch
POST /api/v1/batch/month-end/initiate
Body: {"period_start": "2025-01-01", "period_end": "2025-01-31"}

# Get Status
GET /api/v1/batch/{batch_id}/status

# Get Workers
GET /api/v1/batch/{batch_id}/workers

# Get Metrics
GET /api/v1/batch/{batch_id}/metrics

# Get Validation Results
GET /api/v1/batch/{batch_id}/validation

# Abort Batch
POST /api/v1/batch/{batch_id}/abort
Body: {"reason": "Data quality issue"}

# All endpoints require authentication
Headers: {"Authorization": "Bearer <token>"}
```

### Monitoring Query
```sql
-- Useful monitoring queries

-- 1. Current batch progress
SELECT 
    batch_id,
    status,
    (source_premium_count + source_claims_count) as total_txns,
    actual_je_count,
    ROUND(actual_je_count::numeric / (expected_je_count) * 100, 2) as progress_pct,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - processing_started_at))/60 as elapsed_min
FROM staging_month_end_master
WHERE status IN ('PROCESSING', 'VALIDATING')
ORDER BY processing_started_at DESC
LIMIT 1;

-- 2. Worker status summary
SELECT 
    status,
    COUNT(*) as worker_count,
    AVG(records_per_second) as avg_rps,
    SUM(records_processed) as total_processed
FROM batch_worker_control
WHERE batch_id = '2025-01-MONTHEND'
GROUP BY status;

-- 3. Slow workers
SELECT 
    worker_id,
    records_processed,
    expected_record_count,
    records_per_second,
    last_checkpoint_at
FROM batch_worker_control
WHERE batch_id = '2025-01-MONTHEND'
  AND status = 'RUNNING'
  AND records_per_second < 500
ORDER BY records_per_second;

-- 4. Database performance
SELECT 
    COUNT(*) as active_connections,
    AVG(query_duration) as avg_query_ms
FROM pg_stat_activity
WHERE state = 'active'
  AND datname = current_database();

-- 5. Recent checkpoints
SELECT 
    worker_id,
    records_processed,
    records_per_second,
    eta_seconds,
    checkpoint_at
FROM batch_processing_checkpoint
WHERE batch_id = '2025-01-MONTHEND'
  AND checkpoint_at > CURRENT_TIMESTAMP - INTERVAL '5 minutes'
ORDER BY checkpoint_at DESC
LIMIT 20;
```

