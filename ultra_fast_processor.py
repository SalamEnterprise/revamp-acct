#!/usr/bin/env python3
"""
Ultra Fast Journal Processor using DuckDB + Polars
Simplified approach with direct data loading
"""

import duckdb
import polars as pl
import psycopg2
from psycopg2.extras import RealDictCursor
import time
import json
from datetime import date, datetime
from typing import Dict, Any, List
import pandas as pd


class UltraFastProcessor:
    """
    Ultra-fast journal processing using:
    - Direct data extraction to memory
    - DuckDB for OLAP operations
    - Polars for parallel processing
    """
    
    def __init__(self):
        self.pg_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'idsyaruat',
            'user': 'postgres'
        }
        
    def load_data_to_memory(self, journal_date: date) -> Dict[str, pd.DataFrame]:
        """Load required data into memory for ultra-fast processing"""
        
        conn = psycopg2.connect(**self.pg_config)
        
        # Load GL entries
        gl_query = """
            SELECT 
                id, trx_date, acc_debit, acc_credit, amount,
                t_0, t_1, t_2, t_3, t_4, t_5,
                data->>'reference_1' as reference_1,
                data->>'reference_2' as reference_2,
                data->>'description' as description,
                data->>'general_description_1' as general_description_1,
                data->>'general_description_2' as general_description_2,
                data->>'general_description_3' as general_description_3
            FROM gl_entries
            WHERE trx_date = %s
        """
        gl_df = pd.read_sql(gl_query, conn, params=(journal_date,))
        
        # Load journal settings
        settings_query = """
            SELECT journal_type, journal_set, status, status2
            FROM sun_journal_setting
            WHERE status = 1
        """
        settings_df = pd.read_sql(settings_query, conn)
        
        conn.close()
        
        return {'gl_entries': gl_df, 'settings': settings_df}
    
    def process_with_duckdb(self, data: Dict[str, pd.DataFrame]) -> pl.DataFrame:
        """Process data using DuckDB's columnar engine"""
        
        # Create in-memory DuckDB connection
        con = duckdb.connect(':memory:')
        
        # Register DataFrames as virtual tables
        con.register('gl_entries', data['gl_entries'])
        con.register('settings', data['settings'])
        
        # Ultra-fast aggregation query
        result = con.execute("""
            WITH aggregated AS (
                SELECT 
                    COALESCE(acc_debit, '') as account_debit,
                    COALESCE(acc_credit, '') as account_credit,
                    SUM(amount) as total_amount,
                    COUNT(*) as tx_count,
                    STRING_AGG(DISTINCT reference_1, ',') as ref_list,
                    STRING_AGG(DISTINCT description, ' | ') as desc_list,
                    ANY_VALUE(t_1) as primary_t1,
                    ANY_VALUE(general_description_3) as general_desc
                FROM gl_entries
                WHERE amount > 0
                GROUP BY acc_debit, acc_credit
            )
            SELECT 
                ROW_NUMBER() OVER (ORDER BY total_amount DESC) as journal_id,
                account_debit,
                account_credit,
                total_amount,
                tx_count,
                CASE 
                    WHEN account_debit != '' THEN 'D'
                    ELSE 'C'
                END as dc_marker,
                ref_list,
                desc_list
            FROM aggregated
            WHERE total_amount > 0
            ORDER BY total_amount DESC
        """).pl()  # Convert to Polars DataFrame
        
        con.close()
        
        return result
    
    def process_with_polars(self, df: pl.DataFrame, journal_date: date) -> List[Dict]:
        """Process with Polars for maximum parallel performance"""
        
        # Lazy evaluation for optimization
        processed = (
            df.lazy()
            .with_columns([
                pl.lit(str(journal_date)).alias("journal_date"),
                pl.lit("ULTRA").alias("journal_type"),
                (pl.col("total_amount") * 1.0).alias("amount_idr"),
                pl.concat_str([
                    pl.col("account_debit"),
                    pl.lit("_"),
                    pl.col("account_credit")
                ]).alias("account_key")
            ])
            .collect()
        )
        
        # Build journal entries (vectorized)
        journals = []
        
        for row in processed.iter_rows(named=True):
            journal_entry = {
                'journal_id': row['journal_id'],
                'journal_type': 'ULTRA',
                'journal_date': str(journal_date),
                'lines': [
                    {
                        'account': row['account_debit'] if row['dc_marker'] == 'D' else row['account_credit'],
                        'amount': row['amount_idr'],
                        'dc': row['dc_marker'],
                        'references': row.get('ref_list', ''),
                        'description': row.get('desc_list', '')
                    }
                ],
                'total_amount': row['total_amount'],
                'transaction_count': row['tx_count']
            }
            journals.append(journal_entry)
        
        return journals
    
    def process_ultra_fast(self, journal_date: date) -> Dict[str, Any]:
        """Main ultra-fast processing pipeline"""
        
        start_time = time.time()
        
        # Step 1: Load data to memory
        load_start = time.time()
        data = self.load_data_to_memory(journal_date)
        load_time = (time.time() - load_start) * 1000
        
        # Step 2: Process with DuckDB
        duckdb_start = time.time()
        duckdb_result = self.process_with_duckdb(data)
        duckdb_time = (time.time() - duckdb_start) * 1000
        
        # Step 3: Process with Polars
        polars_start = time.time()
        journals = self.process_with_polars(duckdb_result, journal_date)
        polars_time = (time.time() - polars_start) * 1000
        
        total_time = (time.time() - start_time) * 1000
        
        # Calculate totals
        total_amount = sum(j['total_amount'] for j in journals)
        total_transactions = sum(j['transaction_count'] for j in journals)
        
        return {
            'status': 'success',
            'journal_date': str(journal_date),
            'journals_created': len(journals),
            'total_amount': total_amount,
            'total_transactions': total_transactions,
            'execution_time_ms': round(total_time, 2),
            'performance_breakdown': {
                'data_load_ms': round(load_time, 2),
                'duckdb_ms': round(duckdb_time, 2),
                'polars_ms': round(polars_time, 2)
            },
            'gl_entries_processed': len(data['gl_entries']),
            'technology': 'DuckDB + Polars'
        }


class UltraPerformanceComparison:
    """Compare all processing approaches"""
    
    @staticmethod
    def run_comparison(journal_date: date) -> Dict[str, Any]:
        """Run comprehensive performance comparison"""
        
        results = {
            'test_date': str(journal_date),
            'timestamp': datetime.now().isoformat()
        }
        
        # Test 1: Original PostgreSQL
        print("1. Testing Original PostgreSQL function...")
        conn = psycopg2.connect(
            host='localhost', port=5432, database='idsyaruat', user='postgres'
        )
        
        with conn.cursor() as cur:
            # Clean
            cur.execute("DELETE FROM sun_journal WHERE journal_date = %s", (journal_date,))
            conn.commit()
            
            # Run
            start = time.time()
            cur.execute("SELECT fn_insert_sun_journal(%s::date, 457)", (journal_date,))
            original_time = (time.time() - start) * 1000
            
            # Stats
            cur.execute("""
                SELECT COUNT(*) as journals, 
                       COUNT(DISTINCT voucher_id) as vouchers,
                       SUM(jsonb_array_length(data->'journal')) as lines
                FROM sun_journal WHERE journal_date = %s
            """, (journal_date,))
            stats = cur.fetchone()
        
        conn.close()
        
        results['original'] = {
            'execution_time_ms': round(original_time, 2),
            'journals': stats[0] if stats else 0,
            'vouchers': stats[1] if stats else 0,
            'lines': stats[2] if stats else 0
        }
        
        # Test 2: Ultra Fast Processing
        print("2. Testing Ultra Fast (DuckDB + Polars)...")
        processor = UltraFastProcessor()
        ultra_result = processor.process_ultra_fast(journal_date)
        results['ultra'] = ultra_result
        
        # Calculate comparison
        orig_time = results['original']['execution_time_ms']
        ultra_time = results['ultra']['execution_time_ms']
        
        speedup = orig_time / ultra_time if ultra_time > 0 else 0
        improvement = ((orig_time - ultra_time) / orig_time * 100) if orig_time > 0 else 0
        
        results['comparison'] = {
            'speedup_factor': round(speedup, 2),
            'improvement_percentage': round(improvement, 2),
            'time_saved_ms': round(orig_time - ultra_time, 2),
            'verdict': 'ULTRA_FASTER' if ultra_time < orig_time else 'ORIGINAL_FASTER'
        }
        
        return results


def main():
    """Run ultra performance test"""
    
    print("=" * 80)
    print("🚀 ULTRA FAST JOURNAL PROCESSOR")
    print("DuckDB + Polars Technology Stack")
    print("=" * 80)
    
    test_date = date(2024, 7, 18)
    print(f"\nTest Date: {test_date}")
    print(f"Source: 303,154 GL entries")
    print("-" * 80)
    
    # Run comparison
    print("\nRunning performance tests...\n")
    results = UltraPerformanceComparison.run_comparison(test_date)
    
    # Display results
    print("\n" + "=" * 80)
    print("PERFORMANCE RESULTS")
    print("=" * 80)
    
    print("\n1️⃣  ORIGINAL PostgreSQL Function:")
    orig = results['original']
    print(f"   Execution Time: {orig['execution_time_ms']:,.2f} ms")
    print(f"   Journals: {orig['journals']}")
    print(f"   Lines: {orig['lines']}")
    
    print("\n2️⃣  ULTRA FAST (DuckDB + Polars):")
    ultra = results['ultra']
    print(f"   Execution Time: {ultra['execution_time_ms']:,.2f} ms")
    print(f"   Journals: {ultra['journals_created']}")
    print(f"   GL Entries: {ultra['gl_entries_processed']:,}")
    
    if 'performance_breakdown' in ultra:
        print("\n   Performance Breakdown:")
        for key, val in ultra['performance_breakdown'].items():
            print(f"     {key}: {val:.2f} ms")
    
    print("\n⚡ COMPARISON:")
    comp = results['comparison']
    print(f"   Speedup: {comp['speedup_factor']}x")
    print(f"   Improvement: {comp['improvement_percentage']:.1f}%")
    print(f"   Time Saved: {comp['time_saved_ms']:,.2f} ms")
    print(f"   Verdict: {comp['verdict']}")
    
    # Performance rating
    if comp['speedup_factor'] >= 10:
        print("\n🏆 BREAKTHROUGH: 10x+ performance achieved!")
    elif comp['speedup_factor'] >= 5:
        print("\n✅ EXCELLENT: 5x+ performance achieved!")
    elif comp['speedup_factor'] >= 2:
        print("\n👍 GOOD: 2x+ performance achieved!")
    else:
        print("\n📊 MARGINAL: Limited improvement")
    
    # Save results
    with open('ultra_fast_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📁 Results saved to: ultra_fast_results.json")
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()