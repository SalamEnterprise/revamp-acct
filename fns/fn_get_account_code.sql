-- Function: fn_get_account_code
-- Purpose: Get account code based on pattern matching or use lookup
-- Parameters: set_account_code, account_code_lookup (jsonb), data_idx
-- Returns: character varying

CREATE OR REPLACE FUNCTION public.fn_get_account_code(character varying, jsonb, integer)
 RETURNS character varying
 LANGUAGE plpgsql
AS $function$	
DECLARE
 v_set_account_code ALIAS FOR $1;        -- Account code from settings
 v_account_code_lookup ALIAS FOR $2;     -- Account code lookup data (jsonb)
 v_data_idx ALIAS FOR $3;                -- Data index
 v_count_code integer;
 v_account_code character varying;
BEGIN
  -- Check if account code matches predefined patterns
  select into v_count_code count(*)
  where trim(upper(v_set_account_code)) like '%BANK%' 	or 
        trim(upper(v_set_account_code)) like '%PREMI%' 	or
        trim(upper(v_set_account_code)) like '%PIUTANG%'    or
        trim(upper(v_set_account_code)) like '%UTANG%'      or
        trim(upper(v_set_account_code)) like '%KLAIM%' 	or
        trim(upper(v_set_account_code)) like '%KONTRIBUSI%' or
        --trim(upper(v_set_account_code)) like '%TABARRU%' or
        --trim(upper(v_set_account_code)) like '%UJRAH%' 	or 
        trim(upper(v_set_account_code)) like '%RUTIN%' 	or 
        trim(upper(v_set_account_code)) like '%REMUN%' 	or
        trim(upper(v_set_account_code)) like '%FEE%'        or 
        trim(upper(v_set_account_code)) like '%APPROPRIATE%' or
        trim(upper(v_set_account_code)) like '%BIAYA%'      or
        trim(upper(v_set_account_code)) like '%KOMISI%'
		;
    
  -- Use lookup if pattern matches, otherwise use setting code directly
  IF v_count_code>0 THEN 
   v_account_code = (v_account_code_lookup->'account'->>(v_data_idx))::varchar;
  ELSE 
   v_account_code = v_set_account_code;
  END IF;	

  RETURN v_account_code;
  
END;
$function$