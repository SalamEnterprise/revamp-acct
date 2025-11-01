
## 7. API SPECIFICATIONS

### 7.1 Batch Control API

#### 7.1.1 Initiate Batch

```http
POST /api/v1/batch/month-end/initiate
```

**Request:**
```json
{
  "period_start": "2025-01-01",
  "period_end": "2025-01-31",
  "batch_type": "COMBINED",
  "worker_count": 100,
  "dry_run": false
}
```

**Response (202 Accepted):**
```json
{
  "batch_id": "2025-01-MONTHEND",
  "status": "PREPARING",
  "expected_transactions": 10000000,
  "expected_je_count": 30000000,
  "estimated_duration_minutes": 20,
  "monitoring_url": "/api/v1/batch/2025-01-MONTHEND/status"
}
```

**Error Responses:**
- `400 Bad Request` – Invalid parameters  
- `409 Conflict` – Batch already running  
- `503 Service Unavailable` – Prerequisite batch not complete

---

#### 7.1.2 Get Batch Status

```http
GET /api/v1/batch/{batch_id}/status
```

**Response:**
```json
{
  "batch_id": "2025-01-MONTHEND",
  "status": "PROCESSING",
  "phase": "PARALLEL_PROCESSING",
  "progress": {
    "total_transactions": 10000000,
    "processed_transactions": 8234567,
    "percentage": 82.3,
    "workers": {
      "total": 100,
      "running": 98,
      "completed": 0,
      "failed": 2
    }
  },
  "timing": {
    "started_at": "2025-01-31T23:00:00Z",
    "elapsed_seconds": 847,
    "estimated_remaining_seconds": 215,
    "estimated_completion_at": "2025-01-31T23:17:42Z"
  },
  "performance": {
    "current_throughput_per_sec": 9723,
    "average_throughput_per_sec": 9728,
    "peak_throughput_per_sec": 11247
  },
  "validation": {
    "pre_flight": "PASSED",
    "per_worker": "IN_PROGRESS",
    "pre_commit": "PENDING"
  }
}
```

---

#### 7.1.3 Get Worker Status

```http
GET /api/v1/batch/{batch_id}/workers
```

**Response:**
```json
{
  "batch_id": "2025-01-MONTHEND",
  "workers": [
    {
      "worker_id": 1,
      "status": "RUNNING",
      "progress": {
        "records_processed": 98234,
        "expected_records": 100000,
        "percentage": 98.2
      },
      "performance": {
        "records_per_second": 723,
        "elapsed_seconds": 136
      },
      "last_checkpoint": "2025-01-31T23:15:23Z",
      "eta_seconds": 2
    },
    {
      "worker_id": 2,
      "status": "COMPLETED",
      "progress": {
        "records_processed": 100000,
        "expected_records": 100000,
        "percentage": 100.0
      },
      "performance": {
        "records_per_second": 735,
        "elapsed_seconds": 136
      },
      "completed_at": "2025-01-31T23:15:16Z"
    },
    {
      "worker_id": 15,
      "status": "FAILED",
      "error": "Database connection lost",
      "last_checkpoint": "2025-01-31T23:14:45Z",
      "progress": {
        "records_processed": 87234,
        "expected_records": 100000,
        "percentage": 87.2
      },
      "recovery_action": "RESTARTED",
      "replacement_worker_id": 101
    }
  ]
}
```

---

#### 7.1.4 Abort Batch

```http
POST /api/v1/batch/{batch_id}/abort
```

**Request:**
```json
{
  "reason": "Detected data quality issue",
  "rollback": true
}
```

**Response (202 Accepted):**
```json
{
  "batch_id": "2025-01-MONTHEND",
  "status": "ABORTING",
  "message": "Stopping workers and rolling back changes",
  "estimated_rollback_time_seconds": 60
}
```

---

### 7.2 Monitoring & Metrics API

#### 7.2.1 Get Real-Time Metrics

```http
GET /api/v1/batch/{batch_id}/metrics
```

**Response:**
```json
{
  "batch_id": "2025-01-MONTHEND",
  "timestamp": "2025-01-31T23:15:30Z",
  "metrics": {
    "throughput": {
      "current_rps": 9723,
      "average_rps": 9728,
      "peak_rps": 11247,
      "target_rps": 5556
    },
    "latency": {
      "p50_ms": 8.2,
      "p95_ms": 34.7,
      "p99_ms": 67.3,
      "max_ms": 128.5
    },
    "database": {
      "active_connections": 112,
      "max_connections": 250,
      "connection_utilization": 44.8,
      "query_time_avg_ms": 2.3
    },
    "memory": {
      "staging_table_size_mb": 4523,
      "worker_memory_total_mb": 8234,
      "database_cache_hit_rate": 99.2
    }
  }
}
```

---

#### 7.2.2 Get Validation Results

```http
GET /api/v1/batch/{batch_id}/validation
```

**Response:**
```json
{
  "batch_id": "2025-01-MONTHEND",
  "validations": {
    "pre_flight": {
      "status": "PASSED",
      "timestamp": "2025-01-31T23:00:05Z",
      "checks": [
        {
          "name": "prerequisite_batches",
          "status": "PASS",
          "message": "All prerequisite batches completed"
        },
        {
          "name": "source_data_integrity",
          "status": "PASS",
          "message": "10M transactions validated"
        },
        {
          "name": "database_resources",
          "status": "PASS",
          "message": "Sufficient resources available"
        }
      ]
    },
    "pre_commit": {
      "status": "PASSED",
      "timestamp": "2025-01-31T23:17:30Z",
      "checks": [
        {
          "name": "record_count",
          "status": "PASS",
          "expected": 30000000,
          "actual": 30000000,
          "message": "Record count matches"
        },
        {
          "name": "sequence_integrity",
          "status": "PASS",
          "gaps": 0,
          "duplicates": 0,
          "message": "No sequence issues"
        },
        {
          "name": "debit_credit_balance",
          "status": "PASS",
          "total_debit": "10000000000.00",
          "total_credit": "10000000000.00",
          "difference": "0.00",
          "message": "Balanced"
        },
        {
          "name": "fund_totals",
          "status": "PASS",
          "fund_checks": [
            {
              "fund": "TABARRU",
              "expected": "4000000000.00",
              "actual": "4000000000.00",
              "difference": "0.00"
            },
            {
              "fund": "TANAHUD",
              "expected": "4000000000.00",
              "actual": "4000000000.00",
              "difference": "0.00"
            },
            {
              "fund": "UJROH",
              "expected": "2000000000.00",
              "actual": "2000000000.00",
              "difference": "0.00"
            }
          ]
        }
      ]
    }
  }
}
```
