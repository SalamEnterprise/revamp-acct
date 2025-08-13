-- Function: fn_get_row_record_sun_journal_setting
-- Purpose: Get journal row settings configuration from sun_journal_setting table
-- Returns table with journal configuration details

-- Overload 1: Single parameter
CREATE OR REPLACE FUNCTION public.fn_get_row_record_sun_journal_setting(character varying)
 RETURNS TABLE(journal_line_number integer, process_line_number integer, account_code character varying, d_c_marker character, data_idx integer, account_flag integer, t1_code character varying, t2_code character varying, t3_code character varying, t4_code character varying, t5_code character varying, t6_code character varying, t7_code character varying, t8_code character varying, t9_code character varying, t10_code character varying)
 LANGUAGE plpgsql
AS $function$	
DECLARE
 v_journal_type ALIAS FOR $1;
BEGIN
	   RETURN QUERY
	    select * from jsonb_to_recordset((select journal_set->'row' from sun_journal_setting b where b.journal_type=v_journal_type)) 
         as x(journal_line_number integer,process_line_number integer,account_code character varying,d_c_marker character,
				data_idx integer,account_flag integer,
		        t1_code character varying,
				t2_code character varying,
				t3_code character varying,
				t4_code character varying,
				t5_code character varying,
				t6_code character varying,
				t7_code character varying,
				t8_code character varying,
				t9_code character varying,
				t10_code character varying);

END;
$function$

-- Overload 2: Two parameters (includes reversal logic)
CREATE OR REPLACE FUNCTION public.fn_get_row_record_sun_journal_setting(character varying, character varying)
 RETURNS TABLE(journal_line_number integer, process_line_number integer, account_code character varying, d_c_marker character, data_idx integer, account_flag integer, transaction_amount numeric, t1_code character varying, t2_code character varying, t3_code character varying, t4_code character varying, t5_code character varying, t6_code character varying, t7_code character varying, t8_code character varying, t9_code character varying, t10_code character varying)
 LANGUAGE plpgsql
AS $function$	
DECLARE
 v_journal_type ALIAS FOR $1;
 v_journal_id ALIAS FOR $2;
 v_reversal integer;
BEGIN
    
	select into v_reversal mod((substring(v_journal_type,2,1))::integer+2,2);
	
	IF v_reversal = 0 THEN 
	
	   RETURN QUERY
	    select * from jsonb_to_recordset((select journal_set->'row' from sun_journal_setting b where b.journal_type=v_journal_type)) 
         as x(journal_line_number integer,process_line_number integer,account_code character varying,d_c_marker character,
				data_idx integer,account_flag integer,transaction_amount numeric,
		        t1_code character varying,
				t2_code character varying,
				t3_code character varying,
				t4_code character varying,
				t5_code character varying,
				t6_code character varying,
				t7_code character varying,
				t8_code character varying,
				t9_code character varying,
				t10_code character varying);
				
	ELSEIF v_reversal = 1 THEN 
	
        RETURN QUERY	
		with data as (
			select jsonb_array_elements((data->'journal')::jsonb) as data
			from sun_journal
			where id=v_journal_id
		) 
		select 
			(data->'baris'->>3)::integer as journal_line_number, b.process_line_number, 
			(data->'baris'->>7)::varchar as Account_Code, 
			(case when data->'baris'->>13 = 'D' then 'C' else 'D' end)::bpchar as DC_Marker,
			(data->'baris'->>3)::integer-1 as data_idx, b.account_flag,
			(data->'baris'->>10)::numeric as transaction_amount,
			(data->'baris'->>17)::varchar as T1_Kode_Jenis_Dana,
			(data->'baris'->>18)::varchar as T2_Jenis_Polis,
			(data->'baris'->>19)::varchar as T3_Jenis_Product,
			(data->'baris'->>20)::varchar as T4_Saluran_Distribusi,
			(data->'baris'->>21)::varchar as T5_Lokasi,
			(data->'baris'->>22)::varchar as T6_Economy_Sector,
			(data->'baris'->>23)::varchar as T7_Unit,
			(data->'baris'->>24)::varchar as T8_,
			(data->'baris'->>25)::varchar as T9_,
			(data->'baris'->>26)::varchar as T10_
		from data a 
		 left join fn_get_row_record_sun_journal_setting(v_journal_type) b on 
		   (a.data->'baris'->>3)::integer = b.journal_line_number; 
	 	
	END IF;

END;
$function$