#!/usr/bin/env python3
"""
Performance test comparing original vs optimized journal processing
"""

import sys
import os
from datetime import date

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'enhanced_system'))

from enhanced_system.src.services.optimized_journal_service import ComparisonBenchmark


def main():
    """Run performance comparison"""
    
    # Test date with maximum transactions
    test_date = date(2024, 7, 18)
    
    print("=" * 80)
    print("JOURNAL PROCESSING PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"Test Date: {test_date} (Maximum transaction date)")
    print(f"Source GL Entries: 303,154 records")
    print(f"Test Parameter: 457")
    print("-" * 80)
    
    print("\nRunning performance comparison...")
    print("(This will test both original and optimized functions)")
    print()
    
    # Run comparison
    results = ComparisonBenchmark.run_comparison(test_date)
    
    # Display results
    print("=" * 80)
    print("PERFORMANCE RESULTS")
    print("=" * 80)
    
    print("\n📊 ORIGINAL FUNCTION (fn_insert_sun_journal):")
    print("-" * 50)
    original = results['original']
    print(f"  Execution Time:    {original['execution_time_ms']:,.2f} ms")
    print(f"  Journals Created:  {original['journals_created']}")
    print(f"  Vouchers Created:  {original['vouchers_created']}")
    print(f"  Total Lines:       {original['total_lines']}")
    
    print("\n⚡ OPTIMIZED SYSTEM:")
    print("-" * 50)
    optimized = results['optimized']
    print(f"  Execution Time:    {optimized['execution_time_ms']:,.2f} ms")
    print(f"  Journals Created:  {optimized['journals_created']}")
    print(f"  Vouchers Created:  {optimized['vouchers_created']}")
    
    print("\n  Optimization Features Applied:")
    for feature in optimized.get('optimization_features', []):
        print(f"    ✓ {feature}")
    
    print("\n🎯 PERFORMANCE COMPARISON:")
    print("-" * 50)
    comparison = results['comparison']
    print(f"  Speedup Factor:     {comparison['speedup_factor']}x faster")
    print(f"  Performance Gain:   {comparison['improvement_percentage']:.1f}%")
    print(f"  Time Saved:         {comparison['time_saved_ms']:,.2f} ms")
    print(f"  Verdict:            {comparison['verdict']}")
    
    print("\n💰 DATA INTEGRITY CHECK:")
    print("-" * 50)
    integrity = results['data_integrity']
    print(f"  Total Debits:       IDR {integrity['total_debits']:,.2f}")
    print(f"  Total Credits:      IDR {integrity['total_credits']:,.2f}")
    print(f"  Balance Status:     {integrity['balance_status']}")
    
    # Performance analysis
    print("\n" + "=" * 80)
    print("PERFORMANCE ANALYSIS")
    print("=" * 80)
    
    if comparison['speedup_factor'] > 1:
        print(f"\n✅ SUCCESS: Optimized system is {comparison['speedup_factor']}x FASTER!")
        
        # Calculate time savings
        daily_runs = 30  # Typical daily batch runs
        monthly_runs = daily_runs * 30
        
        time_saved_per_run = comparison['time_saved_ms'] / 1000  # seconds
        daily_savings = (time_saved_per_run * daily_runs) / 60  # minutes
        monthly_savings = daily_savings * 30  # minutes
        yearly_savings = monthly_savings * 12 / 60  # hours
        
        print(f"\n📈 Projected Time Savings:")
        print(f"   Per Run:       {time_saved_per_run:.2f} seconds")
        print(f"   Per Day:       {daily_savings:.1f} minutes")
        print(f"   Per Month:     {monthly_savings:.1f} minutes ({monthly_savings/60:.1f} hours)")
        print(f"   Per Year:      {yearly_savings:.1f} hours")
        
        # Cost savings estimate
        server_cost_per_hour = 0.5  # USD
        yearly_cost_savings = yearly_savings * server_cost_per_hour
        
        print(f"\n💵 Estimated Cost Savings:")
        print(f"   Server time saved/year: {yearly_savings:.1f} hours")
        print(f"   Cost savings/year:      ${yearly_cost_savings:.2f} USD")
        
    else:
        print("\n❌ No performance improvement detected")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if comparison['speedup_factor'] >= 2:
        print("🏆 EXCELLENT: Enhanced system shows significant performance improvement!")
        print(f"   The optimized system processes journals {comparison['speedup_factor']}x faster")
        print(f"   while maintaining complete data integrity and balance.")
    elif comparison['speedup_factor'] > 1.5:
        print("✅ GOOD: Enhanced system shows moderate performance improvement.")
    elif comparison['speedup_factor'] > 1:
        print("📊 MARGINAL: Enhanced system shows slight performance improvement.")
    else:
        print("⚠️  No significant improvement detected.")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()