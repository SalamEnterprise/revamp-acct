-- Main function: fn_insert_sun_journal(date, integer)
-- Purpose: Create journal entries for insurance transactions and output to CSV for SUN Accounting System
-- Parameters: v_journal_date (date), v_created_by (integer)
-- Returns: integer (return value)

CREATE OR REPLACE FUNCTION public.fn_insert_sun_journal(date, integer)
 RETURNS integer
 LANGUAGE plpgsql
AS $function$
DECLARE
 v_journal_date ALIAS FOR $1;
 v_created_by ALIAS FOR $2;
 v_start_journal_process date;
 s record;
 d record;
 r record;
 j_data jsonb;
 v_baris character varying[];
 v_row character varying; 
 i integer;
 j integer;
 v_max_line integer;
 v_delimiter character;
 v_Transaction_Reference character varying;
 v_Transaction_Amount numeric;
 --v_t7 character varying; 
 v_count_lookup_t5 integer;
 --v_t5 character varying;
 v_account_code character varying[];
 v_account_amount numeric;
 v_t1  character varying;
 v_t2  character varying;
 v_t3  character varying;
 v_t4  character varying;
 v_t5  character varying;
 v_t6  character varying;
 v_t7  character varying;
 v_t8  character varying;
 v_t9  character varying;
 v_t10 character varying;
 v_uuid character varying;
 v_data json;
 v_search_id character varying[];
 v_retval integer;
 n integer;	
BEGIN 
 
 v_start_journal_process = '2019-05-01';

 IF (v_journal_date>=v_start_journal_process) THEN -- and (v_journal_date<=now()::date) 
 
--  v_retval = fn_temp01_life_grup_reas_schedule();
  --v_retval = fn_ins_life_tg_log();
  
  FOR s IN 
  
   select * from sun_journal_setting 
   where status=1 
    and ((journal_set->'start_period' is null or journal_set->'end_period' is null)or  
	     (journal_set->'start_period' is not null and journal_set->'end_period' is not null 
		   and v_journal_date between (journal_set->>'start_period')::date and (journal_set->>'end_period')::date)or
		 (journal_set->'end_period' is not null and status2=1 and v_journal_date>(journal_set->>'end_period')::date))
   order by 1
   
  LOOP
  
   insert into test_table (id,name,kolom1,kolom2,kolom3,kolom4)values --,data_json
   (uuid(),'sun_journal',s.journal_type,s.journal_set->>'ds',v_journal_date::varchar,now()::varchar);
   
   j=0;
   i=0;
   select into v_max_line count(*) from fn_get_row_record_sun_journal_setting(s.journal_type);
  
   FOR d IN  
   
     select * from fn_get_datasource_sun_journal(v_journal_date,(s.journal_set->>'ds')::integer,v_journal_date,v_journal_date)

    LOOP   
	
	 j=j+1;
	 i=0; v_row = '';
	 FOR k IN 1..2 LOOP
		v_account_code[k] = '';
	 END LOOP;
	 FOR l IN 1..v_max_line LOOP
		v_baris[l] = '';
	 END LOOP;
	 
	 v_uuid = uuid();
	 v_data = ('{"journal_type" : "'||s.journal_type||'","journal_id" : "'||v_uuid||'","description" : "'||d.description||'"'||
	           ',"spa_no" : "'||d.General_Description_1||'","policy_no" : "'||d.General_Description_2||'"'||
			   ',"participant_no" : "'||d.General_Description_3||'","invoice_no" : "'||d.General_Description_4||'"'||
			   ',"receipting_no" : "'||d.General_Description_5||'","agen_code" : "'||d.General_Description_6||'"'||
			   '}')::json;
	 v_search_id = array[d.General_Description_3];
	 v_account_amount = 0.0;
      
     FOR r IN 

	  select * from fn_get_row_record_sun_journal_setting(s.journal_type,d.id) order by 2,1
       
     LOOP	 
	 
	   v_Transaction_Reference = substring(replace(d.Transaction_Reference,'.',''),1,15);
	   
	   /*
	   IF (d.Journal_Type = 'S0470' or d.Journal_Type = 'S1470') THEN 
		IF trim(d.Transaction_Reference) = '' THEN 
			v_Transaction_Reference = 'RK Giro';			 
		END IF;
		v_t5 = fn_get_tcode(r.t5_code,d.t5->'t5');
	   ELSE 	
		select into v_count_lookup_t5 count(*)
		from sun_tcode_lookup 
		where analysis_dimension='T5' and analysis_code=fn_get_tcode(r.t5_code,d.t5->'t5');
		IF v_count_lookup_t5>0 THEN 
			v_t5 = fn_get_tcode(r.t5_code,d.t5->'t5');
		ELSE 
			--v_t5 = 'N/A';
			v_t5 = '3174'; --default "Kota Adm Jakarta Selatan"
		END IF;
	   END IF;	
	   */
	   
	   IF r.transaction_amount is not null and r.transaction_amount>0 THEN 
		v_Transaction_Amount = r.transaction_amount; 
	   ELSE 
	    v_Transaction_Amount = round((d.Transaction_Amount->'amount'->>(r.data_idx))::numeric,2); 
	   END IF;	
	   
	-- insert into test_table
	--  (id,name,kolom1,kolom2,kolom3,kolom4)values --,data_json
	--(uuid(),'sun_journal',s.journal_type,d.id,i||', '||v_Transaction_Reference,v_t5);
	   
	   IF v_Transaction_Amount > 0 THEN 
	   
	    --v_account_code = fn_get_account_code(r.Account_Code,d.Account_Code,r.data_idx);
		v_t1  = fn_get_tcode(r.t1_code,d.t1->'t1');
		v_t2  = fn_get_tcode(r.t2_code,d.t2->'t2');
		v_t3  = fn_get_tcode(r.t3_code,d.t3->'t3');
		v_t4  = fn_get_tcode(r.t4_code,d.t4->'t4');
		v_t5  = fn_get_tcode(r.t5_code,d.t5->'t5');
		v_t6  = fn_get_tcode(r.t6_code,d.t6->'t6');
		v_t7  = fn_get_tcode(r.t7_code,d.t7->'t7');
		v_t8  = fn_get_tcode(r.t8_code,d.t8->'t8',r.data_idx);
		v_t9  = fn_get_tcode(r.t9_code,d.t9->'t9',r.data_idx);
		v_t10 = fn_get_tcode(r.t10_code,d.t10->'t10',r.data_idx);
	   
		/*
		i = i+1;
		IF i = 1 THEN 
			v_delimiter = '';
		ELSE
			v_delimiter = ',';
		END IF;
		*/
	   
		v_baris[r.Journal_Line_Number] = '{"baris" : ["'||d.Journal_Type||'","'||d.Journal_Source||'","'||d.Journal_Number||'","'||r.Journal_Line_Number||'",'|| -- i
                          '"'||v_Transaction_Reference||'","'||d.Accounting_Period||'","'||d.Transaction_Date||'",'||
						  '"'||fn_get_account_code(r.Account_Code,d.Account_Code,r.data_idx)||'",'||
						  '"'||regexp_replace(substring(d.Description,1,50), E'[\\0\\n\\r]+', ' ', 'g' )::varchar||'","'||d.Currency_Code||'","'||v_Transaction_Amount||'","'||d.Currency_Rate||'",'||
						  '"'||round(v_Transaction_Amount * d.Currency_Rate , 2)||'",'||
						  '"'||r.d_c_marker||'","'||d.Asset_Indicator||'","'||d.Asset_Code||'","'||d.Asset_Sub_Code||'",'||
						  '"'||v_t1||'","'||v_t2||'","'||v_t3||'",'||
						  '"'||v_t4||'","'||v_t5||'","'||v_t6||'",'||
						  '"'||v_t7||'","'||v_t8||'","'||v_t9||'",'||
						  '"'||v_t10||'",'||  -- '||d.General_Description_1||' 
						  '"","'||d.General_Description_2||'",'||
						  '"'||substring(replace(d.General_Description_3,'.',''),1,30)||'",'||
						  '"'||d.General_Description_4||'",'||
						  '"'||d.General_Description_5||'","'||d.General_Description_6||'","",'||
						  '"","","","","","","","","","",'||
						  '"","","","","","","","",'||
						  '"'||d.Due_Date||'",'||
						  '"","","",""]}'; 
						  
	
		  IF r.d_c_marker='D' THEN 
		   v_account_code[1] = fn_get_account_code(r.Account_Code,d.Account_Code,r.data_idx);
          ELSEIF r.d_c_marker='C' THEN 
		   v_account_code[2] = fn_get_account_code(r.Account_Code,d.Account_Code,r.data_idx);
		  END IF;
    
          --IF r.account_flag=0 THEN 	
		  --ELSE
		  IF r.account_flag=1 THEN 		 
		  
		    v_account_amount = v_Transaction_Amount;
			
			insert into gl_entries
			(trx_id,acc_debit,acc_credit,amount,trx_date,t_1,t_2,t_3, t_4, t_5, t_6, t_7, t_8, t_9, t_10, data)values
			(d.Transaction_Reference,v_account_code[1],v_account_code[2],v_account_amount,v_journal_date,
			 v_t1,v_t2,v_t3,v_t4,v_t5,v_t6,v_t7,v_t8,v_t9,v_t10, v_data);
			 
		  ELSEIF r.account_flag=2 THEN 		 
		    
			v_account_amount = v_Transaction_Amount;
			
		  ELSEIF r.account_flag=3 THEN 		 
		  
			insert into gl_entries
			(trx_id,acc_debit,acc_credit,amount,trx_date,t_1,t_2,t_3, t_4, t_5, t_6, t_7, t_8, t_9, t_10, data)values
			(d.Transaction_Reference,v_account_code[1],v_account_code[2],v_account_amount,v_journal_date,
			 v_t1,v_t2,v_t3,v_t4,v_t5,v_t6,v_t7,v_t8,v_t9,v_t10, v_data);
			 
          ELSEIF r.account_flag=4 THEN 		 
		  
			insert into gl_entries
			(trx_id,acc_debit,acc_credit,amount,trx_date,t_1,t_2,t_3, t_4, t_5, t_6, t_7, t_8, t_9, t_10, data)values
			(d.Transaction_Reference,v_account_code[1],v_account_code[2],v_account_amount,v_journal_date,
			 v_t1,v_t2,v_t3,v_t4,v_t5,v_t6,v_t7,v_t8,v_t9,v_t10, v_data);
             
			v_account_amount = v_Transaction_Amount - v_account_amount; 
		  
		  END IF;
		  
		  
	   END IF; --v_Transaction_Amount					  
						  
	 END LOOP; -- journal_row
	 
	 n = 0;
	 
	 FOR m IN 1..v_max_line LOOP  
	 
	    IF v_baris[m] <> '' THEN 
		  n = n + 1;
		  
		  IF n = 1 THEN 
			v_delimiter = '';
		  ELSE
		  	v_delimiter = ',';
		  END IF;
		
		  v_row = v_row || v_delimiter || v_baris[m];
	    END IF;
	 
	 END LOOP;	
	 
	 j_data = '{"journal" : [' ||v_row|| '],"journal_date" : "'||v_journal_date||'","journal_type" : "'||s.journal_type||'"}';
	 insert into sun_journal (id,source_rowid,data,journal_type,journal_date,created_by,search_id) values(v_uuid,d.id,j_data::jsonb,s.journal_type,v_journal_date,v_created_by,v_search_id);
	 
	 --insert into test_table 
	 -- (id,name,kolom1)values --,kolom2,kolom3,kolom4,data_json
	 -- (uuid(),'sun_journal',d.id);
	 
   END LOOP; -- datasource 
   
   insert into test_table (id,name,kolom1,kolom2,kolom3,kolom4)values --,data_json
   (uuid(),'sun_journal',s.journal_type,'count: ('||j||','||v_max_line||')',v_journal_date::varchar,now()::varchar);
   
  END LOOP; -- journal_type 
  
  v_retval = fn_insert_sun_voucher(v_journal_date);
  
 ELSE 
  
  v_retval = 1; 
 
 END IF; 
   
  RETURN v_retval;

END;

$function$