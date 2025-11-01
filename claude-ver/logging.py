# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'batch_detailed': {
            'format': (
                '%(asctime)s | %(levelname)-8s | '
                'Batch=%(batch_id)s | Worker=%(worker_id)s | '
                'Phase=%(phase)s | %(message)s'
            )
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': (
                '%(asctime)s %(levelname)s %(name)s '
                '%(batch_id)s %(worker_id)s %(message)s'
            )
        }
    },
    'handlers': {
        'batch_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/batch/month_end.log',
            'maxBytes': 100 * 1024 * 1024,  # 100MB
            'backupCount': 10,
            'formatter': 'batch_detailed'
        },
        'batch_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/batch/month_end_errors.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 5,
            'formatter': 'batch_detailed'
        },
        'metrics': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/batch/metrics.log',
            'maxBytes': 200 * 1024 * 1024,  # 200MB
            'backupCount': 3,
            'formatter': 'json'  # JSON for easy parsing
        }
    },
    'loggers': {
        'batch.orchestrator': {
            'handlers': ['batch_file', 'batch_error'],
            'level': 'INFO',
            'propagate': False
        },
        'batch.worker': {
            'handlers': ['batch_file', 'batch_error'],
            'level': 'INFO',
            'propagate': False
        },
        'batch.validator': {
            'handlers': ['batch_file', 'batch_error'],
            'level': 'INFO',
            'propagate': False
        },
        'batch.metrics': {
            'handlers': ['metrics'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

# Structured Logging
import logging
from pythonjsonlogger import jsonlogger

class BatchLogger:
    """Structured logging for batch operations"""
    
    def __init__(self, component: str, batch_id: str, worker_id: int = None):
        self.logger = logging.getLogger(f'batch.{component}')
        self.batch_id = batch_id
        self.worker_id = worker_id
        self.component = component
    
    def info(self, message: str, **kwargs):
        """Log info with context"""
        extra = {
            'batch_id': self.batch_id,
            'worker_id': self.worker_id,
            'component': self.component,
            **kwargs
        }
        self.logger.info(message, extra=extra)
    
    def error(self, message: str, exc_info=True, **kwargs):
        """Log error with context"""
        extra = {
            'batch_id': self.batch_id,
            'worker_id': self.worker_id,
            'component': self.component,
            **kwargs
        }
        self.logger.error(message, exc_info=exc_info, extra=extra)
    
    def metric(self, metric_name: str, value: float, **kwargs):
        """Log metric"""
        metrics_logger = logging.getLogger('batch.metrics')
        extra = {
            'batch_id': self.batch_id,
            'worker_id': self.worker_id,
            'metric_name': metric_name,
            'metric_value': value,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        }
        metrics_logger.info(f'METRIC: {metric_name}={value}', extra=extra)

# Usage Example
logger = BatchLogger('worker', batch_id='2025-01-MONTHEND', worker_id=15)

logger.info('Worker started', phase='INITIALIZATION')
logger.metric('records_processed', 1000, elapsed_seconds=1.4)
logger.error('Database connection failed', phase='PROCESSING')
```

### 9.2.2 Log Retention Policy
```
Log Retention Strategy:
┌────────────────────────────────────────────────────────┐
│ Log Type        │ Retention │ Rotation    │ Archive   │
├─────────────────┼───────────┼─────────────┼───────────┤
│ Batch Execution │ 90 days   │ Daily       │ Compress  │
│ Error Logs      │ 180 days  │ Weekly      │ Keep all  │
│ Metrics         │ 30 days   │ Daily       │ Delete    │
│ Audit Trail     │ 7 years   │ Monthly     │ Keep all  │
└────────────────────────────────────────────────────────┘

Log Archival Process:
1. Daily: Compress logs older than 7 days (gzip)
2. Weekly: Move logs older than 30 days to archive storage
3. Monthly: Generate batch summary reports
4. Quarterly: Review archive and purge non-essential logs
