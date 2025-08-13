-- Function: fn_get_datasource_sun_journal
-- Purpose: Route to appropriate data source based on journal_id ranges
-- Parameters: journal_date, journal_id, start_period, end_period
-- Returns: Journal data records from various specialized functions

CREATE OR REPLACE FUNCTION public.fn_get_datasource_sun_journal(date, integer, date, date)
 RETURNS TABLE(id character varying, journal_type character varying, journal_source character varying, journal_number text, journal_line_number text, transaction_reference character varying, accounting_period text, transaction_date text, account_code jsonb, description character varying, currency_code character varying, transaction_amount jsonb, currency_rate numeric, base_amount character varying, d_c_marker character varying, asset_indicator character varying, asset_code character varying, asset_sub_code character varying, t1 jsonb, t2 jsonb, t3 jsonb, t4 jsonb, t5 jsonb, t6 jsonb, t7 jsonb, t8 jsonb, t9 jsonb, t10 jsonb, general_description_1 character varying, general_description_2 character varying, general_description_3 character varying, general_description_4 character varying, general_description_5 character varying, general_description_6 character varying, due_date text)
 LANGUAGE plpgsql
AS $function$	
DECLARE
 v_journal_date ALIAS FOR $1;
 v_journal_id ALIAS FOR $2;
 v_start_period ALIAS FOR $3;
 v_end_period ALIAS FOR $4;
BEGIN

 -- Underwriting transactions (1-10, 101-110)
 IF (v_journal_id >= 1 and v_journal_id <= 10)OR 
            (v_journal_id >= 101 and v_journal_id <= 110)
 THEN 
  RETURN QUERY
   select * from fn_get_dssj_underwriting(v_journal_date,v_journal_id);
 
 -- Bank reconciliation (11-30, 111-130) 
 ELSEIF  (v_journal_id >= 11 and v_journal_id <= 30)OR
            (v_journal_id >= 111 and v_journal_id <= 130)
 THEN 
  RETURN QUERY
   select * from fn_get_dssj_bank_reconciliation(v_journal_date,v_journal_id,v_start_period,v_end_period);
   
 -- Bank reconciliation UL (51-70, 151-170)
 ELSEIF  (v_journal_id >= 51 and v_journal_id <= 70)OR
	(v_journal_id >= 151 and v_journal_id <= 170)
 THEN 
  RETURN QUERY
   select * from fn_get_dssj_bank_reconciliation_ul(v_journal_date,v_journal_id,v_start_period,v_end_period);
   
 -- Unit deal UL (91-92, 191-192)
 ELSEIF  (v_journal_id >= 91 and v_journal_id <= 92)OR
            (v_journal_id >= 191 and v_journal_id <= 192)
 THEN 
  RETURN QUERY
   select * from fn_get_dssj_unit_deal_ul(v_journal_date,v_journal_id);
  
 -- Claim process (31-40, 131-140)
 ELSEIF  (v_journal_id >= 31 and v_journal_id <= 40)OR
            (v_journal_id >= 131 and v_journal_id <= 140)  
 THEN 
  RETURN QUERY
   select * from fn_get_dssj_claim_process(v_journal_date,v_journal_id);
   
 -- Claim process UL (71-80, 171-180)
 ELSEIF  (v_journal_id >= 71 and v_journal_id <= 80)OR 
            (v_journal_id >= 171 and v_journal_id <= 180) 
 THEN 
  RETURN QUERY
   select * from fn_get_dssj_claim_process_ul(v_journal_date,v_journal_id);  
 
 -- Claim payment (41-50, 141-150)
 ELSEIF  (v_journal_id >= 41 and v_journal_id <= 50)OR 
            (v_journal_id >= 141 and v_journal_id <= 150) 
 THEN 
  RETURN QUERY
   select * from fn_get_dssj_claim_payment(v_journal_date,v_journal_id);
   
 -- Range 81-90, 181-190 (no implementation)
 ELSEIF  (v_journal_id >= 81 and v_journal_id <= 90)OR
            (v_journal_id >= 181 and v_journal_id <= 190) 
 THEN 
    -- No implementation
    
 -- Appropriate transactions (91-99)
 ELSEIF  v_journal_id >= 91 and v_journal_id <= 99 THEN 
  RETURN QUERY  
	select * from fn_get_dssj_appropriate(v_journal_date,v_journal_id);

 END IF;
 
END;
$function$