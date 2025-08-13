# High-Level Pseudo Code: Insurance Journal Processing System

## Main Function: fn_insert_sun_journal(journal_date, created_by)

```
FUNCTION fn_insert_sun_journal(journal_date, created_by)
BEGIN
    // Business Rule: Only process dates from 2019-05-01 onwards
    IF journal_date < '2019-05-01' THEN
        RETURN 1  // Skip processing
    END IF
    
    // PHASE 1: JOURNAL PROCESSING
    FOR EACH active_journal_setting IN get_active_journal_settings(journal_date) DO
        
        // Initialize processing counters
        SET journal_count = 0
        SET max_lines = get_max_journal_lines(journal_setting.type)
        
        // Get data from appropriate source based on journal type
        FOR EACH source_data IN get_datasource(journal_date, journal_setting) DO
            
            journal_count = journal_count + 1
            
            // Create unique journal entry
            journal_id = generate_uuid()
            account_codes = initialize_account_arrays()
            journal_lines = initialize_line_arrays(max_lines)
            
            // Build journal metadata
            metadata = create_journal_metadata(journal_id, source_data)
            
            // Process each journal line configuration
            FOR EACH line_config IN get_journal_line_config(journal_setting.type, source_data.id) DO
                
                // Extract and validate transaction amount
                amount = get_transaction_amount(line_config, source_data)
                
                IF amount > 0 THEN
                    // Get analysis codes (T1-T10)
                    t_codes = extract_transaction_codes(line_config, source_data)
                    
                    // Build journal line entry (57-field format)
                    journal_line = build_journal_line(
                        source_data, 
                        line_config, 
                        amount, 
                        t_codes
                    )
                    
                    // Store in journal lines array
                    journal_lines[line_config.line_number] = journal_line
                    
                    // Collect account codes for GL processing
                    IF line_config.d_c_marker = 'D' THEN
                        account_codes[1] = get_account_code(line_config, source_data)
                    ELSE IF line_config.d_c_marker = 'C' THEN
                        account_codes[2] = get_account_code(line_config, source_data)
                    END IF
                    
                    // Process GL entries based on account flag
                    SWITCH line_config.account_flag
                        CASE 1: 
                            insert_gl_entry(account_codes, amount, t_codes, metadata)
                        CASE 2:
                            accumulate_amount = amount
                        CASE 3:
                            insert_gl_entry(account_codes, accumulated_amount, t_codes, metadata)
                        CASE 4:
                            insert_gl_entry(account_codes, accumulated_amount, t_codes, metadata)
                            accumulated_amount = amount - accumulated_amount
                    END SWITCH
                END IF
            END FOR
            
            // Consolidate journal lines into JSON structure
            consolidated_lines = consolidate_journal_lines(journal_lines)
            journal_data = create_journal_json(consolidated_lines, journal_date, journal_setting.type)
            
            // Store journal entry
            INSERT INTO sun_journal (id, source_rowid, data, journal_type, journal_date, created_by, search_id)
            VALUES (journal_id, source_data.id, journal_data, journal_setting.type, journal_date, created_by, search_array)
            
        END FOR
        
        // Log processing summary
        log_processing_summary(journal_setting.type, journal_count, max_lines, journal_date)
        
    END FOR
    
    // PHASE 2: VOUCHER CREATION
    voucher_result = fn_insert_sun_voucher(journal_date)
    
    RETURN voucher_result
END FUNCTION
```

## Voucher Creation Function: fn_insert_sun_voucher(journal_date)

```
FUNCTION fn_insert_sun_voucher(journal_date)
BEGIN
    // Get all journal types that need voucher processing
    FOR EACH journal_type_group IN get_unvouchered_journals(journal_date) DO
        
        // Get next voucher sequence number
        max_sequence = get_max_voucher_sequence(journal_type_group.type, journal_date)
        
        // Group journals by common characteristics for voucher consolidation
        FOR EACH voucher_group IN group_journals_for_voucher(journal_type_group) DO
            
            voucher_sequence = max_sequence + 1
            voucher_id = generate_uuid()
            
            // Generate voucher number: TypeYYMMDDSEQQ
            voucher_number = generate_voucher_number(
                voucher_group.journal_type, 
                journal_date, 
                voucher_sequence
            )
            
            voucher_lines = []
            
            // Aggregate journal lines by account code and debit/credit marker
            FOR EACH aggregated_line IN aggregate_journal_lines(voucher_group) DO
                
                // Build voucher line in 57-field format
                voucher_line = build_voucher_line(
                    voucher_group,
                    aggregated_line,
                    voucher_number
                )
                
                voucher_lines.append(voucher_line)
            END FOR
            
            // Create voucher record
            voucher_data = create_voucher_json(voucher_lines)
            INSERT INTO sun_voucher (id, journal_type, journal_date, voucher_no, data)
            VALUES (voucher_id, journal_type_group.type, journal_date, voucher_number, voucher_data)
            
            // Link journals to voucher
            UPDATE sun_journal 
            SET voucher_id = voucher_id 
            WHERE matches_voucher_group(voucher_group) AND voucher_id IS NULL
            
        END FOR
    END FOR
    
    RETURN 0
END FUNCTION
```

## Helper Function Pseudo Code

```
FUNCTION get_active_journal_settings(journal_date)
BEGIN
    RETURN SELECT * FROM sun_journal_setting 
           WHERE status = 1 
           AND date_period_check(journal_date, journal_set)
           ORDER BY journal_type
END FUNCTION

FUNCTION get_datasource(journal_date, journal_setting)
BEGIN
    data_source_id = journal_setting.journal_set.ds
    RETURN route_to_datasource_function(journal_date, data_source_id)
END FUNCTION

FUNCTION route_to_datasource_function(journal_date, data_source_id)
BEGIN
    SWITCH data_source_id_range(data_source_id)
        CASE underwriting_range: RETURN fn_get_dssj_underwriting(...)
        CASE bank_recon_range: RETURN fn_get_dssj_bank_reconciliation(...)
        CASE claim_process_range: RETURN fn_get_dssj_claim_process(...)
        // ... other ranges
    END SWITCH
END FUNCTION

FUNCTION get_account_code(line_config, source_data)
BEGIN
    IF account_code_needs_lookup(line_config.account_code) THEN
        RETURN lookup_account_code(source_data.account_code, line_config.data_idx)
    ELSE
        RETURN line_config.account_code
    END IF
END FUNCTION

FUNCTION get_transaction_amount(line_config, source_data)
BEGIN
    IF line_config.transaction_amount > 0 THEN
        RETURN line_config.transaction_amount
    ELSE
        RETURN round(source_data.transaction_amount[line_config.data_idx], 2)
    END IF
END FUNCTION
```

## Data Flow Summary

1. **Input**: journal_date, created_by
2. **Configuration Load**: Active journal settings with period validation
3. **Data Routing**: Route to specialized data source functions by ID ranges
4. **Journal Processing**: Create detailed journal entries with analysis codes
5. **GL Integration**: Post to internal GL based on account flags
6. **Voucher Consolidation**: Group and aggregate journal entries
7. **CSV Export Preparation**: Format for SUN Accounting System
8. **Output**: Status code and voucher linking