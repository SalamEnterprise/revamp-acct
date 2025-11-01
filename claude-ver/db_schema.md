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
  
