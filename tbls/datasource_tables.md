# Data Source Tables

## Referenced Functions for Data Sources
These functions are called by fn_get_datasource_sun_journal based on journal_id ranges:

### Underwriting Data Sources (ID: 1-10, 101-110)
- **Function**: fn_get_dssj_underwriting
- **Purpose**: Processes underwriting transactions
- **Data Sources**: Premium, policy, and underwriting related tables

### Bank Reconciliation Data Sources (ID: 11-30, 111-130)
- **Function**: fn_get_dssj_bank_reconciliation
- **Purpose**: Bank reconciliation processing
- **Parameters**: journal_date, journal_id, start_period, end_period
- **Data Sources**: Bank transaction and reconciliation tables

### Bank Reconciliation UL Data Sources (ID: 51-70, 151-170)
- **Function**: fn_get_dssj_bank_reconciliation_ul
- **Purpose**: Unit Link bank reconciliation
- **Data Sources**: Unit link bank transaction tables

### Unit Deal UL Data Sources (ID: 91-92, 191-192)
- **Function**: fn_get_dssj_unit_deal_ul
- **Purpose**: Unit link investment transactions
- **Data Sources**: Unit investment and dealing tables

### Claim Process Data Sources (ID: 31-40, 131-140)
- **Function**: fn_get_dssj_claim_process
- **Purpose**: Claim processing transactions
- **Data Sources**: Claim processing and approval tables

### Claim Process UL Data Sources (ID: 71-80, 171-180)
- **Function**: fn_get_dssj_claim_process_ul
- **Purpose**: Unit link claim processing
- **Data Sources**: Unit link specific claim tables

### Claim Payment Data Sources (ID: 41-50, 141-150)
- **Function**: fn_get_dssj_claim_payment
- **Purpose**: Claim payment transactions
- **Data Sources**: Claim payment and disbursement tables

### Appropriate Data Sources (ID: 91-99)
- **Function**: fn_get_dssj_appropriate
- **Purpose**: Appropriation and allocation transactions
- **Data Sources**: Fund appropriation tables

## Data Source Return Structure
All data source functions return a consistent table structure with fields:
- id, journal_type, journal_source, journal_number
- transaction_reference, accounting_period, transaction_date
- account_code (jsonb), description, currency_code
- transaction_amount (jsonb), currency_rate, base_amount
- d_c_marker, asset_indicator, asset_code, asset_sub_code
- t1 through t10 (jsonb) - Analysis dimensions
- general_description_1 through general_description_6
- due_date