#!/usr/bin/env python3
"""
Test script to benchmark enhanced journal processing system
"""

import asyncio
import json
from datetime import date
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'enhanced_system'))

from enhanced_system.src.services.enhanced_journal_service import (
    EnhancedJournalService,
    JournalBenchmarkService
)


async def main():
    """Run benchmark test"""
    
    # Test date with maximum transactions
    test_date = date(2024, 7, 18)
    
    print("=" * 80)
    print("ENHANCED JOURNAL PROCESSING SYSTEM - PERFORMANCE BENCHMARK")
    print("=" * 80)
    print(f"Test Date: {test_date}")
    print(f"Test Parameter: 457")
    print("-" * 80)
    
    # Run full benchmark
    print("\nStarting benchmark test...")
    results = await JournalBenchmarkService.run_benchmark(test_date)
    
    # Display results
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)
    
    print("\n1. ORIGINAL SYSTEM:")
    print("-" * 40)
    original = results.get('original', {})
    print(f"   Execution Time: {original.get('execution_time_ms', 0):.2f} ms")
    print(f"   Journals Created: {original.get('journals_created', 0)}")
    print(f"   Vouchers Created: {original.get('vouchers_created', 0)}")
    
    print("\n2. ENHANCED SYSTEM:")
    print("-" * 40)
    enhanced = results.get('enhanced', {})
    print(f"   Execution Time: {enhanced.get('execution_time_ms', 0):.2f} ms")
    print(f"   Journals Created: {enhanced.get('journals_created', 0)}")
    print(f"   Vouchers Created: {enhanced.get('vouchers_created', 0)}")
    
    if 'performance_gain' in enhanced:
        gain = enhanced['performance_gain']
        print(f"\n   Performance Gain:")
        print(f"   - Speedup Factor: {gain.get('speedup_factor', 0)}x")
        print(f"   - Improvement: {gain.get('improvement_percentage', 0):.1f}%")
    
    print("\n3. COMPARISON:")
    print("-" * 40)
    comparison = results.get('comparison', {})
    print(f"   Speedup Factor: {comparison.get('speedup_factor', 0)}x")
    print(f"   Improvement: {comparison.get('improvement_percentage', 0):.1f}%")
    print(f"   Time Saved: {comparison.get('time_saved_ms', 0):.2f} ms")
    print(f"   Verdict: {comparison.get('verdict', 'N/A')}")
    
    # Save detailed results
    output_file = 'benchmark_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✅ Detailed results saved to: {output_file}")
    
    # Additional performance metrics
    print("\n" + "=" * 80)
    print("PERFORMANCE ANALYSIS")
    print("=" * 80)
    
    if comparison.get('speedup_factor', 0) > 1:
        print(f"✅ Enhanced system is {comparison['speedup_factor']}x FASTER")
        print(f"✅ Performance improved by {comparison['improvement_percentage']:.1f}%")
        
        # Calculate projected savings
        daily_runs = 10  # Assume 10 runs per day
        monthly_runs = daily_runs * 30
        time_saved_daily = (comparison['time_saved_ms'] * daily_runs) / 1000 / 60  # minutes
        time_saved_monthly = time_saved_daily * 30
        
        print(f"\n📊 Projected Time Savings:")
        print(f"   - Per Day ({daily_runs} runs): {time_saved_daily:.1f} minutes")
        print(f"   - Per Month: {time_saved_monthly:.1f} minutes ({time_saved_monthly/60:.1f} hours)")
        print(f"   - Per Year: {time_saved_monthly*12/60:.1f} hours")
    else:
        print("❌ Enhanced system did not show improvement")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())