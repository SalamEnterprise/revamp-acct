-- Function: fn_get_tcode
-- Purpose: Get transaction code from JSON data or use default
-- Returns: character varying

CREATE OR REPLACE FUNCTION public.fn_get_tcode(character varying, jsonb)
 RETURNS character varying
 LANGUAGE plpgsql
AS $function$	
DECLARE
 v_tcode_js ALIAS FOR $1;  -- Transaction code from settings
 v_tcode_ds ALIAS FOR $2;  -- Transaction code from data source
 v_tcode character varying;
BEGIN
  -- Use setting code if available, otherwise use first element from data source
  IF v_tcode_js is not null THEN -- and v_tcode_js <> ''
    v_tcode = v_tcode_js;
  ELSE 
    v_tcode = (v_tcode_ds->>0)::varchar; 
  END IF;	

  -- Default to 'N/A' if empty
  IF trim(v_tcode) = '' THEN 
	v_tcode = 'N/A';
  END IF;
  
  RETURN v_tcode;
  
END;
$function$