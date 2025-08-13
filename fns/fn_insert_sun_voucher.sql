-- Function: fn_insert_sun_voucher
-- Purpose: Create voucher entries from journal data for final CSV export
-- Parameters: journal_date
-- Returns: integer

CREATE OR REPLACE FUNCTION public.fn_insert_sun_voucher(date)
 RETURNS integer
 LANGUAGE plpgsql
AS $function$	
DECLARE
 v_journal_date ALIAS FOR $1;
 s record;
 d record;
 r record;
 j record;
 j_data jsonb;
 v_row character varying; 
 i integer;
 v_delimiter character;
 v_Transaction_Reference character varying;
 v_Description character varying;
 --v_t7 character varying; 
 v_count_lookup_t5 integer;
 v_t5 character varying;
 v_max_voucher_no character varying;
 v_max_voucher_seq integer;
 v_voucher_id character varying;
 v_voucher_no character varying;
BEGIN 
  
  -- Process each journal type that hasn't been assigned to a voucher yet
  FOR s IN 
  
   select a.data->>'journal_type' as journal_type, b.description  
   from sun_journal a 
    left join sun_journal_setting b on a.data->>'journal_type' = b.journal_type
   where (data->>'journal_date')::date = v_journal_date and voucher_id is null
   group by 1,2
   order by 1
   
  LOOP
  
    -- Get next voucher sequence number
    select into v_max_voucher_no max(substring(voucher_no,12,4))
	from sun_voucher
	where journal_type=s.journal_type and journal_date=v_journal_date;
	
	IF v_max_voucher_no is not null THEN 
	 v_max_voucher_seq = v_max_voucher_no::integer;
	ELSE 
	 v_max_voucher_seq = 0;
	END IF;
  	
	-- Group journal entries by common characteristics for voucher creation
	FOR d IN 
	
	 with data as (
	  select json_array_elements((data->'journal')::json) as data
	  	from sun_journal
	  	where data->>'journal_type' = s.journal_type and (data->>'journal_date')::date = v_journal_date and voucher_id is null
	  )
	  select 
	  	data->'baris'->>0 as Journal_Type,
	  	data->'baris'->>1 as Journal_Source,
	  	data->'baris'->>2 as Journal_Number,
	  	data->'baris'->>5 as Accounting_Period,
	  	data->'baris'->>6 as Transaction_Date,
		data->'baris'->>9 as Currency_Code,
		data->'baris'->>11 as Currency_Rate,
	  	data->'baris'->>14 as Asset_Indicator,
	  	data->'baris'->>15 as Asset_Code,
		data->'baris'->>16 as Asset_Sub_Code,
		data->'baris'->>17 as t1,
	  	--data->'baris'->>18 as t2,
	  	data->'baris'->>19 as t3,
	  	data->'baris'->>20 as t4,
	  	data->'baris'->>21 as t5,   
	  	--data->'baris'->>22 as t6,
	  	data->'baris'->>23 as t7
		--data->'baris'->>24 as t8,   
	  	--data->'baris'->>25 as t9,
	  	--data->'baris'->>26 as t10
	  from data a 
	  group by 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15--,16--,17,18,19     
	  order by 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15--,16--,17,18,19
	
	LOOP 
	
	 -- Initialize voucher data
	 i=0; v_row = '';
	 v_voucher_id = uuid();
	 v_max_voucher_seq = v_max_voucher_seq + 1;
	 
	 -- Generate voucher number: JournalType + YYMMDD + 4-digit sequence
	 v_voucher_no = d.Journal_Type||substring(extract(year from v_journal_date)::varchar,3,2)||
	                           lpad(extract(month from v_journal_date)::varchar,2,'0')||
							   lpad(extract(day from v_journal_date)::varchar,2,'0')||
							   lpad(v_max_voucher_seq::varchar,4,'0');
     v_Transaction_Reference = v_voucher_no;							   
	 v_Description = substring(s.description ||' '|| v_journal_date ||'/'||lpad(v_max_voucher_seq::varchar,4,'0'),1,50);
      
     -- Aggregate journal lines for this voucher
     FOR r IN 

	  with data as (
		select json_array_elements((data->'journal')::json) as data
		from sun_journal
		where data->>'journal_type' = s.journal_type and (data->>'journal_date')::date = v_journal_date and voucher_id is null
	  )
	  select 
	    data->'baris'->>3 as Journal_Line_Number,
		data->'baris'->>7 as Account_Code,
		sum((data->'baris'->>10)::numeric) as Transaction_Amount,
		sum((data->'baris'->>12)::numeric) as Base_Amount,
		data->'baris'->>13 as d_c_marker,
		data->'baris'->>18 as t2,
		data->'baris'->>22 as t6,
		data->'baris'->>24 as t8,
		data->'baris'->>25 as t9,
		data->'baris'->>26 as t10
	  from data a
	  where 
	    data->'baris'->>0  = d.Journal_Type
	  	and data->'baris'->>1  = d.Journal_Source
	  	and data->'baris'->>2  = d.Journal_Number
	  	and data->'baris'->>5  = d.Accounting_Period
	  	and data->'baris'->>6  = d.Transaction_Date
		and data->'baris'->>9  = d.Currency_Code
		and data->'baris'->>11 = d.Currency_Rate
	  	and data->'baris'->>14 = d.Asset_Indicator
	  	and data->'baris'->>15 = d.Asset_Code
		and data->'baris'->>16 = d.Asset_Sub_Code
		and data->'baris'->>17 = d.t1
	  	--and data->'baris'->>18 = d.t2
	  	and data->'baris'->>19 = d.t3
	  	and data->'baris'->>20 = d.t4
	  	and data->'baris'->>21 = d.t5   
	  	--and data->'baris'->>22 = d.t6
	  	and data->'baris'->>23 = d.t7
	  group by 1,2,5,6,7,8,9,10
	  order by 1,2,5,6,7,8,9,10
        
     LOOP	 
	 
	  i = i+1;
	  IF i = 1 THEN 
	    v_delimiter = '';
	  ELSE
	    v_delimiter = ',';
      END IF;	
	   
	   -- Build voucher line JSON
	   v_row = v_row || v_delimiter ||'{"baris" : ["'||d.Journal_Type||'","'||d.Journal_Source||'","'||d.Journal_Number||'","'||r.Journal_Line_Number||'",'|| --0-3
                          '"'||v_Transaction_Reference||'","'||d.Accounting_Period||'","'||d.Transaction_Date||'",'|| --4-6
						  '"'||r.Account_Code||'",'|| --7
						  '"'||v_Description||'","'||d.Currency_Code||'","'||round(r.Transaction_Amount,2)||'","'||d.Currency_Rate||'",'|| --11
						  '"'||round(r.Base_Amount,2)||'",'|| --12 
						  '"'||r.d_c_marker||'","'||d.Asset_Indicator||'","'||d.Asset_Code||'","'||d.Asset_Sub_Code||'",'|| --16 
						  '"'||d.t1||'","'||r.t2||'","'||d.t3||'",'|| --19
						  '"'||d.t4||'","'||d.t5||'","'||r.t6||'",'|| --22
						  '"'||d.t7||'","'||r.t8||'","'||r.t9||'","'||r.t10||'",'|| --26 23 
						  '"","","","","","","",'|| --33
						  '"","","","","","","","","","",'|| --43
						  '"","","","","","","","",'|| --51
						  --'"'||d.Due_Date||'",'|| --52
						  '"",'|| --52
						  '"","","",""]}'; --57 
						  
	 END LOOP; -- journal_row
	 	 
	 -- Insert voucher record
	 j_data = '{"journal" : [' ||v_row|| ']}';   --,"journal_date" : "'||v_journal_date||'","journal_type" : "'||s.journal_type||'"}';
	 insert into sun_voucher(id,journal_type,journal_date,voucher_no,data) values(v_voucher_id,s.journal_type,v_journal_date,v_voucher_no,j_data::jsonb); --d.Journal_Type
	 
	 -- Update sun_journal records to link them to the voucher
	 FOR j IN 

	  with data as (
		select id,json_array_elements((data->'journal')::json) as data
		from sun_journal
		where data->>'journal_type' = s.journal_type and (data->>'journal_date')::date = v_journal_date and voucher_id is null
	  )
	  select id from data a
	  where 
	    data->'baris'->>0  = d.Journal_Type
	  	and data->'baris'->>1  = d.Journal_Source
	  	and data->'baris'->>2  = d.Journal_Number
	  	and data->'baris'->>5  = d.Accounting_Period
	  	and data->'baris'->>6  = d.Transaction_Date
		and data->'baris'->>9  = d.Currency_Code
		and data->'baris'->>11 = d.Currency_Rate
	  	and data->'baris'->>14 = d.Asset_Indicator
	  	and data->'baris'->>15 = d.Asset_Code
		and data->'baris'->>16 = d.Asset_Sub_Code
		and data->'baris'->>17 = d.t1
	  	--and data->'baris'->>18 = d.t2
	  	and data->'baris'->>19 = d.t3
	  	and data->'baris'->>20 = d.t4
	  	and data->'baris'->>21 = d.t5   
	  	--and data->'baris'->>22 = d.t6
	  	and data->'baris'->>23 = d.t7
	  group by 1
        
     LOOP
	  
	  update sun_journal set voucher_id=v_voucher_id
	  where id=j.id and voucher_id is null;
	 
	 END LOOP;
	 
	END LOOP; -- datasource 
  END LOOP; -- journal type 
   
  RETURN 0;

END;
$function$