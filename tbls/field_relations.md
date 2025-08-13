# Field Names and Table Relations

## Primary Key Relationships

### sun_journal_setting → sun_journal
- **Relation**: sun_journal_setting.journal_type = sun_journal.journal_type
- **Purpose**: Journal configuration lookup

### sun_journal → sun_voucher  
- **Relation**: sun_journal.voucher_id = sun_voucher.id
- **Purpose**: Link journal entries to final vouchers

### sun_journal → gl_entries
- **Relation**: sun_journal.data->'transaction_reference' = gl_entries.trx_id
- **Purpose**: Internal GL tracking

## Key Field Mappings

### Journal Data Structure (JSONB)
```json
{
  "journal_type": "S0XXX",
  "journal_id": "uuid",
  "description": "transaction description",
  "spa_no": "general_description_1",
  "policy_no": "general_description_2", 
  "participant_no": "general_description_3",
  "invoice_no": "general_description_4",
  "receipting_no": "general_description_5",
  "agen_code": "general_description_6"
}
```

### Journal Row Structure (Array of Arrays)
Each journal row contains 57+ fields:
- [0-3]: Journal_Type, Journal_Source, Journal_Number, Journal_Line_Number
- [4-6]: Transaction_Reference, Accounting_Period, Transaction_Date  
- [7]: Account_Code
- [8-12]: Description, Currency_Code, Transaction_Amount, Currency_Rate, Base_Amount
- [13]: D_C_Marker (Debit/Credit)
- [14-16]: Asset_Indicator, Asset_Code, Asset_Sub_Code
- [17-26]: T1-T10 analysis dimensions
- [27-32]: General_Description_1 through General_Description_6
- [33-51]: Reserved fields (mostly empty)
- [52]: Due_Date
- [53-56]: Additional reserved fields

### Analysis Dimensions (T1-T10)
- **T1**: Kode_Jenis_Dana (Fund Type Code)
- **T2**: Jenis_Polis (Policy Type)  
- **T3**: Jenis_Product (Product Type)
- **T4**: Saluran_Distribusi (Distribution Channel)
- **T5**: Lokasi (Location) - Default: '3174' (Jakarta Selatan)
- **T6**: Economy_Sector
- **T7**: Unit
- **T8-T10**: Additional analysis dimensions

## WHERE Clause Relations

### sun_journal_setting filtering:
```sql
WHERE status=1 
AND ((journal_set->'start_period' is null OR journal_set->'end_period' is null)
     OR (journal_set->'start_period' is not null AND journal_set->'end_period' is not null 
         AND v_journal_date BETWEEN (journal_set->>'start_period')::date 
         AND (journal_set->>'end_period')::date)
     OR (journal_set->'end_period' is not null AND status2=1 
         AND v_journal_date>(journal_set->>'end_period')::date))
```

### Data aggregation in voucher creation:
- Groups by: Journal_Type, Journal_Source, Journal_Number, Accounting_Period, Transaction_Date, Currency info, Asset info, T-codes
- Sums: Transaction_Amount, Base_Amount by Account_Code and D_C_Marker

## Account Code Pattern Matching
```sql
-- Patterns that trigger account lookup:
'%BANK%', '%PREMI%', '%PIUTANG%', '%UTANG%', '%KLAIM%', 
'%KONTRIBUSI%', '%RUTIN%', '%REMUN%', '%FEE%', 
'%APPROPRIATE%', '%BIAYA%', '%KOMISI%'
```

## Account Flag Processing Logic
- **Flag 0**: Skip processing (commented out)
- **Flag 1**: Insert to gl_entries immediately
- **Flag 2**: Accumulate amount only
- **Flag 3**: Insert to gl_entries with accumulated amount
- **Flag 4**: Insert to gl_entries then subtract from accumulated amount