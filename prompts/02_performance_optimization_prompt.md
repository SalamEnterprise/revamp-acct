# Performance Optimization Implementation Prompt

## Objective
Implement high-performance enhancements for journal processing system achieving 10-100x speedup.

## Current Performance Baseline
- **Original Function**: ~3,000ms for 300K records
- **Target**: <300ms (10x improvement minimum)

## Implementation Approaches

### Phase 1: Database Optimization (Quick Wins)
```sql
-- 1. Create GIN indexes for JSONB
CREATE INDEX CONCURRENTLY idx_sun_journal_data_gin 
ON sun_journal USING GIN (data);

-- 2. Composite indexes for common queries
CREATE INDEX CONCURRENTLY idx_sun_journal_date_type 
ON sun_journal (journal_date, journal_type);

-- 3. Partial indexes for unvouchered journals
CREATE INDEX CONCURRENTLY idx_sun_journal_unvouchered 
ON sun_journal (journal_date, journal_type) 
WHERE voucher_id IS NULL;
```

Expected improvement: 20-30%

### Phase 2: Modern Python Architecture
```python
# Technology Stack
- FastAPI for async REST API
- SQLAlchemy 2.0 with async support
- Pydantic for validation
- Redis for caching
- Celery for background processing
```

Implementation structure:
```
enhanced_system/
├── src/
│   ├── models/       # Domain models
│   ├── services/     # Business logic
│   ├── api/          # FastAPI endpoints
│   └── core/         # Configuration
├── database/         # SQL optimizations
└── tests/           # Performance tests
```

### Phase 3: Ultra-Performance with DuckDB + Polars
```python
# Revolutionary approach using:
# - DuckDB: In-memory OLAP (C++ speed)
# - Polars: Rust-based DataFrames
# - Arrow: Zero-copy columnar format

class UltraPerformanceProcessor:
    def process_with_duckdb(self, date):
        # Load data with COPY BINARY (10x faster)
        # Process with columnar engine
        # Return Arrow table (zero-copy)
        
    def process_with_polars(self, arrow_table):
        # Parallel processing with Rust speed
        # Vectorized operations
        # Lazy evaluation
```

Expected improvement: 10-100x

## Performance Testing Protocol

### 1. Benchmark Original
```bash
EXPLAIN (ANALYZE, BUFFERS) 
SELECT fn_insert_sun_journal('2024-07-18'::date, 457);
```

### 2. Test Enhanced System
```python
# Measure each component
start = time.time()
result = processor.process_journals(date)
print(f"Time: {(time.time() - start) * 1000}ms")
```

### 3. Compare Results
| Metric | Original | Enhanced | Improvement |
|--------|----------|----------|-------------|
| Time   | 3000ms   | ?ms      | ?x          |
| I/O    | 850K     | ?        | ?%          |
| Memory | 500MB    | ?        | ?%          |

## Bottleneck Solutions

### Problem: Data Loading (90% of time)
```python
# Solution 1: PostgreSQL COPY BINARY
def load_with_copy_binary(date):
    copy_sql = f"""
    COPY (SELECT * FROM gl_entries WHERE trx_date = '{date}')
    TO STDOUT WITH (FORMAT BINARY)
    """
    # 10x faster than SELECT

# Solution 2: Materialized Views
CREATE MATERIALIZED VIEW mv_gl_daily AS
SELECT ... WITH DATA;
# Query pre-aggregated data

# Solution 3: Redis Caching
@cache(ttl=3600)
def get_gl_entries(date):
    # Check cache first
    # Load only if needed
```

### Problem: Processing Speed
```python
# Solution: Vectorized Operations
# Instead of:
for row in data:
    process(row)  # Slow

# Use:
df.apply(vectorized_process)  # Fast
```

## Success Metrics

### Must Have
- [ ] 5x performance improvement
- [ ] Maintained data integrity
- [ ] Backward compatibility
- [ ] Comprehensive testing

### Nice to Have
- [ ] 10x+ performance
- [ ] Real-time processing
- [ ] Horizontal scalability
- [ ] ML-based optimization

## Deployment Checklist
1. Apply database indexes
2. Deploy Python services
3. Run parallel testing
4. Monitor performance
5. Document improvements

## Expected Outcomes
- **Immediate**: 20-40% improvement with indexes
- **Short-term**: 5-10x with Python optimization
- **Long-term**: 10-100x with DuckDB/Polars