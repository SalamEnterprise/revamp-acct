# Business Logic Analysis: Insurance Journal System

## High-Level System Purpose
The system creates accounting journal entries for insurance transactions and exports them to CSV format for integration with SUN Accounting System for financial reporting and compliance.

## Core Business Rules

### 1. Date Validation Rule
- **Rule**: Only process journals for dates >= '2019-05-01'
- **Business Reason**: System cutoff date for new journal processing logic
- **Impact**: Earlier dates return status code 1 (no processing)

### 2. Journal Type Configuration
- **Active Status**: Only process journal_types where status=1
- **Period Controls**: 
  - No period restrictions (start_period and end_period both null)
  - Within valid period range
  - Extended processing (status2=1) for dates after end_period
- **Business Reason**: Flexible control over which journal types are active for different time periods

### 3. Data Source Routing Logic
Journal processing is routed based on ID ranges to specialized functions:
- **1-10, 101-110**: Underwriting transactions (premiums, policies)
- **11-30, 111-130**: Bank reconciliation (payments, receipts)  
- **31-40, 131-140**: Claim processing (claim approvals, adjustments)
- **41-50, 141-150**: Claim payments (disbursements)
- **51-70, 151-170**: Unit Link bank reconciliation
- **71-80, 171-180**: Unit Link claim processing
- **91-92, 191-192**: Unit Link investment transactions
- **91-99**: Fund appropriation transactions

### 4. Account Code Logic
- **Pattern-Based Routing**: Account codes containing specific keywords use dynamic lookup
- **Keywords**: BANK, PREMI, PIUTANG, UTANG, KLAIM, KONTRIBUSI, RUTIN, REMUN, FEE, APPROPRIATE, BIAYA, KOMISI
- **Fallback**: Direct account code usage when pattern doesn't match
- **Business Reason**: Flexible account mapping based on transaction type

### 5. Transaction Amount Processing
- **Priority**: Use setting-defined amount if > 0, otherwise use data source amount
- **Zero Amount Filter**: Only process transactions with amount > 0
- **Precision**: Round to 2 decimal places for consistency

### 6. Analysis Dimensions (T1-T10)
- **T1**: Fund type classification
- **T2**: Policy type classification  
- **T3**: Product type classification
- **T4**: Distribution channel
- **T5**: Geographic location (default: Jakarta Selatan '3174')
- **T6-T10**: Additional analysis dimensions
- **Purpose**: Multi-dimensional reporting and analysis capability

### 7. GL Entry Creation Logic (account_flag)
- **Flag 1**: Immediate GL entry creation
- **Flag 2**: Amount accumulation only (deferred posting)
- **Flag 3**: GL entry with accumulated amount
- **Flag 4**: GL entry then amount adjustment
- **Business Reason**: Complex transaction processing with staged posting

## Business Flow Structure

### Phase 1: Journal Entry Creation
1. Validate processing date
2. Get active journal configurations
3. Route to appropriate data source function
4. Process each transaction:
   - Generate unique journal ID
   - Build journal metadata
   - Process journal lines with T-code analysis
   - Create GL entries based on account flags
   - Store in sun_journal table

### Phase 2: Voucher Consolidation  
1. Group journal entries by common characteristics
2. Generate sequential voucher numbers
3. Aggregate transaction amounts by account
4. Create consolidated voucher entries
5. Link journals to vouchers
6. Store in sun_voucher table

### Phase 3: Export Preparation
- Voucher data is structured for CSV export
- 57-field format matching SUN Accounting System requirements
- Maintains audit trail through voucher_id linkage

## Business Rules Compliance

### Audit Requirements
- **Traceability**: Every transaction linked from source to voucher
- **Immutability**: Journal entries preserved after voucher creation
- **Unique IDs**: UUID-based identification for audit trails

### Financial Controls
- **Debit/Credit Validation**: D_C_Marker ensures proper double-entry
- **Amount Precision**: Consistent 2-decimal rounding
- **Currency Handling**: Multi-currency support with exchange rates

### Integration Points
- **SUN System**: CSV export format compliance
- **Source Systems**: Multiple data source integration
- **GL System**: Internal general ledger maintenance