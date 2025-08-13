# Main Tables Used in Journal Processing System

## Core Journal Tables

### sun_journal_setting
- **Purpose**: Configuration table for journal types and their settings
- **Key Fields**: 
  - journal_type (varchar)
  - status (integer)
  - status2 (integer)
  - journal_set (jsonb) - Contains configuration including:
    - start_period, end_period (dates)
    - ds (data source ID)
    - row (journal row configuration)
- **Usage**: Controls which journal types are active and their processing rules

### sun_journal
- **Purpose**: Stores processed journal entries before voucher creation
- **Key Fields**:
  - id (varchar/uuid)
  - source_rowid (varchar)
  - data (jsonb) - Contains journal entry details
  - journal_type (varchar)
  - journal_date (date)
  - created_by (integer)
  - search_id (varchar[])
  - voucher_id (varchar) - Links to sun_voucher

### sun_voucher
- **Purpose**: Final voucher entries ready for CSV export
- **Key Fields**:
  - id (varchar/uuid)
  - journal_type (varchar)
  - journal_date (date)
  - voucher_no (varchar) - Generated voucher number
  - data (jsonb) - Aggregated journal lines

### gl_entries
- **Purpose**: General ledger entries for internal tracking
- **Key Fields**:
  - trx_id (varchar)
  - acc_debit (varchar)
  - acc_credit (varchar)
  - amount (numeric)
  - trx_date (date)
  - t_1 through t_10 (varchar) - Transaction codes
  - data (json) - Additional transaction data

## Lookup and Reference Tables

### sun_tcode_lookup
- **Purpose**: Transaction code validation and lookup
- **Key Fields**:
  - analysis_dimension (varchar) - e.g., 'T5'
  - analysis_code (varchar)

## Utility Tables

### test_table
- **Purpose**: Development/testing table for debugging
- **Key Fields**:
  - id (varchar)
  - name (varchar)
  - kolom1, kolom2, kolom3, kolom4 (varchar)