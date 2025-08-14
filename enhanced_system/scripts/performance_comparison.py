#!/usr/bin/env python3
"""
Performance Comparison Script
Benchmarks original vs enhanced system performance
"""

import asyncio
import time
import statistics
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

import asyncpg
import psycopg2
from tabulate import tabulate
import matplotlib.pyplot as plt
import pandas as pd


class PerformanceBenchmark:
    """Performance benchmarking for journal system"""
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.results = {
            'original': [],
            'enhanced': []
        }
    
    async def run_benchmark(self, test_dates: List[date]) -> Dict[str, Any]:
        """Run complete benchmark suite"""
        
        print("=" * 80)
        print("INSURANCE JOURNAL SYSTEM PERFORMANCE BENCHMARK")
        print("=" * 80)
        print(f"Test dates: {len(test_dates)} days")
        print(f"Date range: {test_dates[0]} to {test_dates[-1]}")
        print("-" * 80)
        
        # Test original system
        print("\n1. Testing ORIGINAL System (PL/pgSQL Functions)...")
        original_results = await self.benchmark_original_system(test_dates)
        
        # Test enhanced system
        print("\n2. Testing ENHANCED System (Optimized Functions)...")
        enhanced_results = await self.benchmark_enhanced_system(test_dates)
        
        # Compare results
        print("\n3. Analyzing Results...")
        comparison = self.compare_results(original_results, enhanced_results)
        
        # Generate report
        self.generate_report(comparison)
        
        return comparison
    
    async def benchmark_original_system(self, test_dates: List[date]) -> Dict[str, Any]:
        """Benchmark original PL/pgSQL functions"""
        
        conn = await asyncpg.connect(**self.db_config)
        results = []
        
        try:
            for test_date in test_dates:
                # Warm up cache
                await conn.fetchval(
                    "SELECT fn_insert_sun_journal($1, $2)",
                    test_date, 1
                )
                
                # Actual benchmark
                start_time = time.perf_counter()
                
                result = await conn.fetchval(
                    "SELECT fn_insert_sun_journal($1, $2)",
                    test_date, 1
                )
                
                execution_time = (time.perf_counter() - start_time) * 1000  # ms
                
                # Count results
                journal_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM sun_journal WHERE journal_date = $1",
                    test_date
                )
                
                voucher_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM sun_voucher WHERE journal_date = $1",
                    test_date
                )
                
                results.append({
                    'date': test_date,
                    'execution_time_ms': execution_time,
                    'journals': journal_count,
                    'vouchers': voucher_count,
                    'status': 'SUCCESS' if result == 0 else 'FAILED'
                })
                
                print(f"  {test_date}: {execution_time:.2f}ms - {journal_count} journals, {voucher_count} vouchers")
        
        finally:
            await conn.close()
        
        return {
            'system': 'original',
            'results': results,
            'avg_time': statistics.mean([r['execution_time_ms'] for r in results]),
            'median_time': statistics.median([r['execution_time_ms'] for r in results]),
            'min_time': min([r['execution_time_ms'] for r in results]),
            'max_time': max([r['execution_time_ms'] for r in results]),
            'total_journals': sum([r['journals'] for r in results]),
            'total_vouchers': sum([r['vouchers'] for r in results])
        }
    
    async def benchmark_enhanced_system(self, test_dates: List[date]) -> Dict[str, Any]:
        """Benchmark enhanced optimized functions"""
        
        conn = await asyncpg.connect(**self.db_config)
        results = []
        
        try:
            for test_date in test_dates:
                # Warm up cache
                await conn.fetch(
                    "SELECT * FROM fn_insert_sun_journal_optimized($1, $2)",
                    test_date, 1
                )
                
                # Actual benchmark
                start_time = time.perf_counter()
                
                result_row = await conn.fetchrow(
                    "SELECT * FROM fn_insert_sun_journal_optimized($1, $2)",
                    test_date, 1
                )
                
                execution_time = (time.perf_counter() - start_time) * 1000  # ms
                
                results.append({
                    'date': test_date,
                    'execution_time_ms': execution_time,
                    'journals': result_row['journals_created'] if result_row else 0,
                    'vouchers': result_row['vouchers_created'] if result_row else 0,
                    'status': 'SUCCESS' if result_row and result_row['status_code'] == 0 else 'FAILED'
                })
                
                print(f"  {test_date}: {execution_time:.2f}ms - {results[-1]['journals']} journals, {results[-1]['vouchers']} vouchers")
        
        finally:
            await conn.close()
        
        return {
            'system': 'enhanced',
            'results': results,
            'avg_time': statistics.mean([r['execution_time_ms'] for r in results]),
            'median_time': statistics.median([r['execution_time_ms'] for r in results]),
            'min_time': min([r['execution_time_ms'] for r in results]),
            'max_time': max([r['execution_time_ms'] for r in results]),
            'total_journals': sum([r['journals'] for r in results]),
            'total_vouchers': sum([r['vouchers'] for r in results])
        }
    
    def compare_results(self, original: Dict, enhanced: Dict) -> Dict[str, Any]:
        """Compare performance between systems"""
        
        improvement = {
            'avg_improvement': (original['avg_time'] - enhanced['avg_time']) / original['avg_time'] * 100,
            'median_improvement': (original['median_time'] - enhanced['median_time']) / original['median_time'] * 100,
            'speedup_factor': original['avg_time'] / enhanced['avg_time'],
            'original': original,
            'enhanced': enhanced
        }
        
        return improvement
    
    def generate_report(self, comparison: Dict[str, Any]):
        """Generate detailed performance report"""
        
        print("\n" + "=" * 80)
        print("PERFORMANCE COMPARISON REPORT")
        print("=" * 80)
        
        # Summary table
        summary_data = [
            ["Metric", "Original System", "Enhanced System", "Improvement"],
            ["Average Time (ms)", 
             f"{comparison['original']['avg_time']:.2f}",
             f"{comparison['enhanced']['avg_time']:.2f}",
             f"{comparison['avg_improvement']:.1f}%"],
            ["Median Time (ms)",
             f"{comparison['original']['median_time']:.2f}",
             f"{comparison['enhanced']['median_time']:.2f}",
             f"{comparison['median_improvement']:.1f}%"],
            ["Min Time (ms)",
             f"{comparison['original']['min_time']:.2f}",
             f"{comparison['enhanced']['min_time']:.2f}",
             "-"],
            ["Max Time (ms)",
             f"{comparison['original']['max_time']:.2f}",
             f"{comparison['enhanced']['max_time']:.2f}",
             "-"],
            ["Speedup Factor", "-", "-", f"{comparison['speedup_factor']:.2f}x"],
        ]
        
        print("\nSUMMARY:")
        print(tabulate(summary_data, headers="firstrow", tablefmt="grid"))
        
        # Detailed metrics
        print("\nDETAILED METRICS:")
        print(f"Total Journals Processed:")
        print(f"  Original: {comparison['original']['total_journals']}")
        print(f"  Enhanced: {comparison['enhanced']['total_journals']}")
        print(f"\nTotal Vouchers Created:")
        print(f"  Original: {comparison['original']['total_vouchers']}")
        print(f"  Enhanced: {comparison['enhanced']['total_vouchers']}")
        
        # Performance improvement analysis
        print("\nPERFORMANCE IMPROVEMENT ANALYSIS:")
        if comparison['speedup_factor'] >= 5:
            print(f"✅ EXCELLENT: {comparison['speedup_factor']:.1f}x faster!")
            print("   The enhanced system shows exceptional performance gains.")
        elif comparison['speedup_factor'] >= 3:
            print(f"✅ VERY GOOD: {comparison['speedup_factor']:.1f}x faster!")
            print("   The enhanced system shows significant performance improvements.")
        elif comparison['speedup_factor'] >= 2:
            print(f"✅ GOOD: {comparison['speedup_factor']:.1f}x faster!")
            print("   The enhanced system shows noticeable performance improvements.")
        elif comparison['speedup_factor'] > 1:
            print(f"✅ IMPROVED: {comparison['speedup_factor']:.1f}x faster")
            print("   The enhanced system shows moderate performance improvements.")
        else:
            print("⚠️  No significant improvement detected")
        
        # Generate visualization
        self.create_visualization(comparison)
    
    def create_visualization(self, comparison: Dict[str, Any]):
        """Create performance comparison charts"""
        
        try:
            import matplotlib.pyplot as plt
            
            # Prepare data
            original_times = [r['execution_time_ms'] for r in comparison['original']['results']]
            enhanced_times = [r['execution_time_ms'] for r in comparison['enhanced']['results']]
            dates = [r['date'] for r in comparison['original']['results']]
            
            # Create figure with subplots
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle('Journal System Performance Comparison', fontsize=16)
            
            # 1. Time series comparison
            ax1 = axes[0, 0]
            ax1.plot(dates, original_times, 'r-', label='Original', linewidth=2)
            ax1.plot(dates, enhanced_times, 'g-', label='Enhanced', linewidth=2)
            ax1.set_xlabel('Date')
            ax1.set_ylabel('Execution Time (ms)')
            ax1.set_title('Execution Time Comparison')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. Bar chart comparison
            ax2 = axes[0, 1]
            metrics = ['Avg', 'Median', 'Min', 'Max']
            original_values = [
                comparison['original']['avg_time'],
                comparison['original']['median_time'],
                comparison['original']['min_time'],
                comparison['original']['max_time']
            ]
            enhanced_values = [
                comparison['enhanced']['avg_time'],
                comparison['enhanced']['median_time'],
                comparison['enhanced']['min_time'],
                comparison['enhanced']['max_time']
            ]
            
            x = range(len(metrics))
            width = 0.35
            ax2.bar([i - width/2 for i in x], original_values, width, label='Original', color='red', alpha=0.7)
            ax2.bar([i + width/2 for i in x], enhanced_values, width, label='Enhanced', color='green', alpha=0.7)
            ax2.set_xlabel('Metric')
            ax2.set_ylabel('Time (ms)')
            ax2.set_title('Performance Metrics Comparison')
            ax2.set_xticks(x)
            ax2.set_xticklabels(metrics)
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # 3. Distribution histogram
            ax3 = axes[1, 0]
            ax3.hist(original_times, bins=20, alpha=0.5, label='Original', color='red')
            ax3.hist(enhanced_times, bins=20, alpha=0.5, label='Enhanced', color='green')
            ax3.set_xlabel('Execution Time (ms)')
            ax3.set_ylabel('Frequency')
            ax3.set_title('Execution Time Distribution')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # 4. Improvement percentage
            ax4 = axes[1, 1]
            improvements = [
                (orig - enh) / orig * 100 
                for orig, enh in zip(original_times, enhanced_times)
            ]
            ax4.bar(range(len(improvements)), improvements, color='blue', alpha=0.7)
            ax4.axhline(y=comparison['avg_improvement'], color='red', linestyle='--', 
                       label=f"Avg: {comparison['avg_improvement']:.1f}%")
            ax4.set_xlabel('Test Run')
            ax4.set_ylabel('Improvement (%)')
            ax4.set_title('Performance Improvement per Run')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save figure
            filename = f"performance_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(filename, dpi=100)
            print(f"\n📊 Visualization saved to: {filename}")
            
        except ImportError:
            print("\n⚠️  Matplotlib not available for visualization")


async def main():
    """Main benchmark execution"""
    
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'idsyaruat',
        'user': 'postgres',
        'password': None  # Add password if needed
    }
    
    # Generate test dates (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    test_dates = [start_date + timedelta(days=i) for i in range(31)]
    
    # Run benchmark
    benchmark = PerformanceBenchmark(db_config)
    results = await benchmark.run_benchmark(test_dates)
    
    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)
    print(f"\n🎯 Overall Performance Improvement: {results['speedup_factor']:.2f}x faster")
    print(f"💾 Average time reduced from {results['original']['avg_time']:.2f}ms to {results['enhanced']['avg_time']:.2f}ms")
    print(f"📈 Performance gain: {results['avg_improvement']:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())