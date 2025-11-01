## Database connection recovery
```python
class DatabaseConnectionManager:
    """Manage database connections with retry logic"""
    
    def __init__(self, max_retries: int = 5):
        self.max_retries = max_retries
    
    def execute_with_retry(self, operation: Callable, *args, **kwargs):
        """Execute database operation with exponential backoff retry"""
        
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
                
            except OperationalError as e:
                if 'connection' in str(e).lower():
                    # Connection error - retry
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(
                            f'Database connection lost. '
                            f'Retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})'
                        )
                        time.sleep(wait_time)
                        
                        # Reset connection
                        connection.close()
                        
                        continue
                    else:
                        # Max retries exceeded
                        logger.error(
                            f'Database connection failed after {self.max_retries} attempts'
                        )
                        raise
                else:
                    # Non-connection error - don't retry
                    raise

# Usage in worker
db_manager = DatabaseConnectionManager(max_retries=5)

# Wrap database operations
je_headers = db_manager.execute_with_retry(
    StagingJEHeader.objects.bulk_create,
    headers_list,
    batch_size=1000
)
```
### Rollback Procedures
```python
class BatchRollbackManager:
    """Manage batch rollback operations"""
    
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
    
    def rollback_batch(self, reason: str) -> bool:
        """Rollback entire batch"""
        
        logger.critical(
            f'ROLLBACK INITIATED for batch {self.batch_id}. Reason: {reason}'
        )
        
        try:
            with transaction.atomic():
                # Step 1: Check if already committed
                master = StagingMonthEndMaster.objects.get(batch_id=self.batch_id)
                
                if master.status == 'COMMITTED':
                    # Already committed - need special rollback
                    return self.rollback_committed_batch()
                
                # Step 2: Mark batch as failed
                master.status = 'FAILED'
                master.save()
                
                # Step 3: Stop all running workers
                self.stop_all_workers()
                
                # Step 4: Clean staging tables
                self.clean_staging_tables()
                
                # Step 5: Log rollback
                self.log_rollback(reason)
                
                logger.info(f'Batch {self.batch_id} rolled back successfully')
                
                return True
                
        except Exception as e:
            logger.error(
                f'Rollback failed for batch {self.batch_id}: {e}',
                exc_info=True
            )
            return False
    
    def rollback_committed_batch(self) -> bool:
        """Rollback batch that was already committed to production"""
        
        logger.critical(
            f'COMMITTED BATCH ROLLBACK for {self.batch_id}. '
            f'This requires manual intervention!'
        )
        
        with transaction.atomic():
            # Step 1: Delete journal entries
            deleted_headers = JournalEntryHeader.objects.filter(
                batch_id=self.batch_id
            ).delete()
            
            # JournalEntryLine will cascade delete
            
            # Step 2: Reverse fund balance changes
            self.reverse_fund_balance_changes()
            
            # Step 3: Reset source transactions
            PremiumTransaction.objects.filter(
                batch_id=self.batch_id
            ).update(
                batch_processed=False,
                batch_id=None,
                je_created_at=None
            )
            
            ClaimsTransaction.objects.filter(
                batch_id=self.batch_id
            ).update(
                batch_processed=False,
                batch_id=None,
                je_created_at=None
            )
            
            # Step 4: Update master record
            master = StagingMonthEndMaster.objects.get(batch_id=self.batch_id)
            master.status = 'ROLLED_BACK'
            master.save()
            
            logger.critical(
                f'Committed batch {self.batch_id} rolled back. '
                f'Deleted {deleted_headers[0]} journal entries.'
            )
            
            # Step 5: Send critical notification
            self.send_rollback_notification()
            
            return True
    
    def reverse_fund_balance_changes(self):
        """Reverse fund balance changes from batch"""
        
        # Calculate fund changes from journal entries
        fund_changes = JournalEntryLine.objects.filter(
            je__batch_id=self.batch_id
        ).values('fund_type').annotate(
            net_change=Sum('credit_amount') - Sum('debit_amount')
        )
        
        # Reverse changes
        for change in fund_changes:
            FundBalance.objects.filter(
                fund_type=change['fund_type']
            ).update(
                current_balance=F('current_balance') - change['net_change']
            )
```
## Data Integrity and safeguards
### Checksum and veriication
```python
class DataIntegrityChecker:
    """Verify data integrity throughout batch process"""
    
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
    
    def generate_source_checksum(self) -> str:
        """Generate checksum of source data"""
        
        # Hash of all source transaction IDs and amounts
        premium_data = PremiumTransaction.objects.filter(
            batch_processed=False,
            payment_date__range=(self.period_start, self.period_end)
        ).values_list('txn_id', 'premium_amount').order_by('txn_id')
        
        claims_data = ClaimsTransaction.objects.filter(
            batch_processed=False,
            claim_date__range=(self.period_start, self.period_end)
        ).values_list('claim_id', 'claim_amount').order_by('claim_id')
        
        hasher = hashlib.sha256()
        
        for txn_id, amount in premium_data:
            hasher.update(f'{txn_id}:{amount}'.encode())
        
        for claim_id, amount in claims_data:
            hasher.update(f'{claim_id}:{amount}'.encode())
        
        checksum = hasher.hexdigest()
        
        # Store checksum
        master = StagingMonthEndMaster.objects.get(batch_id=self.batch_id)
        master.source_data_checksum = checksum
        master.save()
        
        return checksum
    
    def verify_staging_integrity(self) -> bool:
        """Verify staging data matches source"""
        
        # Check 1: Record count
        expected_je_count = (
            PremiumTransaction.objects.filter(
                batch_processed=False,
                payment_date__range=(self.period_start, self.period_end)
            ).count() * 3
        )
        
        actual_je_count = StagingJEHeader.objects.filter(
            batch_id=self.batch_id
        ).count()
        
        if expected_je_count != actual_je_count:
            logger.error(
                f'Record count mismatch: expected {expected_je_count}, '
                f'got {actual_je_count}'
            )
            return False
        
        # Check 2: Amount reconciliation
        source_total = PremiumTransaction.objects.filter(
            batch_processed=False,
            payment_date__range=(self.period_start, self.period_end)
        ).aggregate(Sum('premium_amount'))['premium_amount__sum']
        
        staging_total = StagingJEHeader.objects.filter(
            batch_id=self.batch_id
        ).aggregate(Sum('total_debit'))['total_debit__sum']
        
        # Should be equal (premiums appear as debits)
        if abs(float(source_total or 0) - float(staging_total or 0)) > 0.01:
            logger.error(
                f'Amount mismatch: source {source_total}, '
                f'staging {staging_total}'
            )
            return False
        
        return True
```
### Atomic Operations

```sql
-- Atomic Commit Pattern
-- CRITICAL: All-or-nothing guarantee

BEGIN TRANSACTION;

-- Set transaction isolation level
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- Lock staging tables to prevent concurrent modifications
LOCK TABLE staging_je_header IN EXCLUSIVE MODE;
LOCK TABLE staging_je_line IN EXCLUSIVE MODE;

-- Verify data integrity one final time
DO $$
DECLARE
    expected_count BIGINT;
    actual_count BIGINT;
BEGIN
    -- Get expected count
    SELECT expected_je_count INTO expected_count
    FROM staging_month_end_master
    WHERE batch_id = '2025-01-MONTHEND';
    
    -- Get actual count
    SELECT COUNT(*) INTO actual_count
    FROM staging_je_header
    WHERE batch_id = '2025-01-MONTHEND';
    
    -- Verify
    IF expected_count != actual_count THEN
        RAISE EXCEPTION 'Record count mismatch: expected %, got %', 
                        expected_count, actual_count;
    END IF;
END $$;

-- If we got here, data is valid. Commit to production.

-- Insert headers
INSERT INTO journal_entry_header (
    je_number, je_date, je_type, reference_type, reference_id,
    description, total_debit, total_credit, status,
    coa_version_id, template_code, created_by, posted_by, posted_at,
    batch_id, batch_created_at
)
SELECT 
    je_number, je_date, je_type, source_type, source_id,
    description, total_debit, total_credit, 'POSTED',
    1, template_code, 'BATCH_SYSTEM', 'BATCH_SYSTEM', CURRENT_TIMESTAMP,
    batch_id, CURRENT_TIMESTAMP
FROM staging_je_header
WHERE batch_id = '2025-01-MONTHEND'
  AND status = 'VALIDATED';

-- Get returned row count
GET DIAGNOSTICS @inserted_headers = ROW_COUNT;

-- Insert lines
INSERT INTO journal_entry_line (
    je_id, line_number, account_code, fund_type,
    debit_amount, credit_amount, description
)
SELECT 
    jeh.je_id,
    sl.line_number,
    sl.account_code,
    sl.fund_type,
    sl.debit_amount,
    sl.credit_amount,
    sl.description
FROM staging_je_line sl
JOIN staging_je_header sh ON sl.staging_header_id = sh.staging_header_id
JOIN journal_entry_header jeh ON sh.je_number = jeh.je_number
WHERE sl.batch_id = '2025-01-MONTHEND';

-- Update fund balances
UPDATE fund_balance
SET 
    current_balance = current_balance + fund_changes.net_change,
    last_updated = CURRENT_TIMESTAMP,
    updated_by = 'BATCH_SYSTEM'
FROM (
    SELECT 
        fund_type,
        SUM(credit_amount) - SUM(debit_amount) as net_change
    FROM journal_entry_line
    WHERE je_id IN (
        SELECT je_id FROM journal_entry_header 
        WHERE batch_id = '2025-01-MONTHEND'
    )
    GROUP BY fund_type
) fund_changes
WHERE fund_balance.fund_type = fund_changes.fund_type;

-- Mark source transactions as processed
UPDATE premium_transaction
SET 
    batch_processed = TRUE,
    batch_id = '2025-01-MONTHEND',
    je_created_at = CURRENT_TIMESTAMP
WHERE payment_date BETWEEN '2025-01-01' AND '2025-01-31'
  AND batch_processed = FALSE;

-- Update batch master
UPDATE staging_month_end_master
SET 
    status = 'COMMITTED',
    committed_at = CURRENT_TIMESTAMP,
    actual_je_count = @inserted_headers
WHERE batch_id = '2025-01-MONTHEND';

-- If ANY error occurred, entire transaction rolls back automatically
-- If we reach here, everything succeeded. Commit!
COMMIT;

-- After commit, archive staging data (separate transaction)
BEGIN;
-- Move staging to archive
INSERT INTO staging_je_header_archive 
SELECT * FROM staging_je_header 
WHERE batch_id = '2025-01-MONTHEND';

-- Truncate staging
TRUNCATE TABLE staging_je_header CASCADE;
TRUNCATE TABLE staging_je_line;

COMMIT;
```

## 11. SECURITY & AUDIT
### 11.1 Security Requirements
#### 11.1.1 Access Control
```python
# Role-Based Access Control for Batch System

BATCH_PERMISSIONS = {
    'batch_admin': [
        'initiate_batch',
        'abort_batch',
        'rollback_batch',
        'view_all_batches',
        'modify_batch_config'
    ],
    'batch_operator': [
        'view_batch_status',
        'view_worker_status',
        'restart_failed_worker',
        'view_validation_results'
    ],
    'finance_viewer': [
        'view_batch_status',
        'view_validation_results',
        'download_batch_reports'
    ],
    'auditor': [
        'view_all_batches',
        'view_audit_trail',
        'export_audit_logs',
        'view_validation_results'
    ]
}

class BatchSecurityMixin:
    """Security mixin for batch operations"""
    
    def check_permission(self, user, permission: str) -> bool:
        """Check if user has permission"""
        
        user_roles = user.groups.values_list('name', flat=True)
        
        for role in user_roles:
            if permission in BATCH_PERMISSIONS.get(role, []):
                return True
        
        return False
    
    def require_permission(self, permission: str):
        """Decorator for permission checking"""
        
        def decorator(func):
            def wrapper(self, request, *args, **kwargs):
                if not self.check_permission(request.user, permission):
                    raise PermissionDenied(
                        f'User does not have permission: {permission}'
                    )
                return func(self, request, *args, **kwargs)
            return wrapper
        return decorator

# Usage
class BatchInitiateView(BatchSecurityMixin, View):
    
    @require_permission('initiate_batch')
    def post(self, request):
        # Only batch_admin can initiate batch
        pass
```
### Audit Train
```python
class AuditTrail:
    """Comprehensive audit trail for batch operations"""
    
    @staticmethod
    def log_operation(
        batch_id: str,
        operation: str,
        user: str,
        details: Dict,
        status: str = 'SUCCESS'
    ):
        """Log audit event"""
        
        AuditLog.objects.create(
            batch_id=batch_id,
            operation=operation,
            performed_by=user,
            performed_at=datetime.utcnow(),
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
            operation_details=details,
            status=status
        )
    
    @staticmethod
    def log_batch_lifecycle(batch_id: str, event: str, details: Dict = None):
        """Log batch lifecycle event"""
        
        BatchLifecycleLog.objects.create(
            batch_id=batch_id,
            event=event,
            event_time=datetime.utcnow(),
            details=details or {}
        )

# Audit Log Model
class AuditLog(models.Model):
    """Audit trail for batch operations"""
    
    audit_id = models.BigAutoField(primary_key=True)
    batch_id = models.CharField(max_length=50, db_index=True)
    
    # Operation details
    operation = models.CharField(max_length=100)
    performed_by = models.CharField(max_length=100)
    performed_at = models.DateTimeField(db_index=True)
    
    # User context
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Operation data
    operation_details = models.JSONField()
    status = models.CharField(max_length=20)  # SUCCESS, FAILED
    
    # Additional context
    before_state = models.JSONField(null=True)
    after_state = models.JSONField(null=True)
    
    class Meta:
        db_table = 'audit_batch_operations'
        indexes = [
            models.Index(fields=['batch_id', 'performed_at']),
            models.Index(fields=['performed_by', 'performed_at']),
            models.Index(fields=['operation', 'performed_at'])
        ]

# Usage throughout system
AuditTrail.log_operation(
    batch_id='2025-01-MONTHEND',
    operation='BATCH_INITIATED',
    user=request.user.username,
    details={
        'period_start': '2025-01-01',
        'period_end': '2025-01-31',
        'worker_count': 100
    },
    status='SUCCESS'
)
```
### Data Privacy
```python
# Sensitive Data Handling

class SensitiveDataHandler:
    """Handle sensitive data in logs and monitoring"""
    
    @staticmethod
    def mask_sensitive_data(data: Dict) -> Dict:
        """Mask sensitive fields in data"""
        
        sensitive_fields = [
            'account_number',
            'policy_holder_id',
            'ssn',
            'tax_id'
        ]
        
        masked_data = data.copy()
        
        for field in sensitive_fields:
            if field in masked_data:
                value = str(masked_data[field])
                if len(value) > 4:
                    masked_data[field] = '*' * (len(value) - 4) + value[-4:]
                else:
                    masked_data[field] = '****'
        
        return masked_data
    
    @staticmethod
    def anonymize_for_logging(record: Dict) -> Dict:
        """Anonymize data for logging"""
        
        # Remove personally identifiable information
        anonymous_record = record.copy()
        
        pii_fields = ['name', 'email', 'phone', 'address']
        
        for field in pii_fields:
            if field in anonymous_record:
                del anonymous_record[field]
        
        return anonymous_record

# Usage in logging
logger_data = SensitiveDataHandler.mask_sensitive_data({
    'policy_id': 12345,
    'account_number': '1234567890',
    'premium_amount': 1000000
})

logger.info('Processing premium', extra=logger_data)
# Logs: Processing premium - account_number: ******7890
```

### Unit Testing
```python
# Test batch components in isolation

import pytest
from decimal import Decimal
from datetime import date

class TestBatchWorker:
    """Unit tests for batch worker"""
    
    @pytest.fixture
    def worker(self):
        """Create test worker"""
        return BatchWorker(
            worker_id=1,
            batch_id='TEST-BATCH',
            sequence_start=1000,
            sequence_end=2000,
            source_start=0,
            source_end=100
        )
    
    def test_sequence_allocation(self, worker):
        """Test worker uses correct sequence range"""
        
        # Worker should start at 1000
        assert worker.sequence_current == 1000
        
        # Get next sequence
        seq = worker.get_next_sequence()
        assert seq == 1000
        
        # Current should increment
        assert worker.sequence_current == 1001
    
    def test_sequence_exhaustion(self, worker):
        """Test worker handles sequence exhaustion"""
        
        # Use all sequences
        worker.sequence_current = worker.sequence_end
        
        # Next sequence should raise error
        with pytest.raises(SequenceExhaustedError):
            worker.get_next_sequence()
    
    def test_je_generation(self, worker, premium_transaction):
        """Test journal entry generation"""
        
        entries = worker.generate_premium_journal_entries(premium_transaction)
        
        # Should generate 3 entries
        assert len(entries) == 3
        
        # Each entry should balance
        for entry in entries:
            total_debit = sum(line['debit_amount'] for line in entry['lines'])
            total_credit = sum(line['credit_amount'] for line in entry['lines'])
            assert total_debit == total_credit
    
    def test_checkpoint_creation(self, worker):
        """Test checkpoint creation"""
        
        worker.control_record = Mock()
        worker.checkpoint(records_processed=1000, last_source_id=5000)
        
        # Should update control record
        assert worker.control_record.records_processed == 1000
        assert worker.control_record.last_source_id_processed == 5000
```
#### Integration Test
```python
class TestBatchIntegration:
    """Integration tests for batch system"""
    
    @pytest.fixture
    def test_database(self):
        """Setup test database"""
        # Use separate test database
        with override_settings(DATABASES={'default': TEST_DB_CONFIG}):
            yield
    
    def test_end_to_end_batch(self, test_database):
        """Test complete batch flow"""
        
        # Setup: Create test data
        self.create_test_premiums(count=1000)
        
        # Execute batch
        orchestrator = BatchOrchestrator(
            batch_id='TEST-BATCH',
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31)
        )
        
        result = orchestrator.execute_batch()
        
        # Verify results
        assert result.status == 'SUCCESS'
        assert result.je_created == 3000  # 1000 premiums × 3 JE each
        
        # Verify database state
        je_count = JournalEntryHeader.objects.filter(
            batch_id='TEST-BATCH'
        ).count()
        assert je_count == 3000
        
        # Verify fund balances updated
        fund_balance = FundBalance.objects.get(fund_type='TABARRU')
        assert fund_balance.current_balance > 0
    
    def test_worker_failure_recovery(self, test_database):
        """Test worker failure and recovery"""
        
        # Setup
        self.create_test_premiums(count=1000)
        
        orchestrator = BatchOrchestrator(
            batch_id='TEST-RECOVERY',
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31)
        )
        
        # Simulate worker failure after 500 records
        with patch('batch.worker.BatchWorker.process_premium_transactions') as mock_process:
            def fail_at_500(*args, **kwargs):
                if mock_process.call_count == 1:
                    # First call: process 500 then fail
                    raise ConnectionError('Simulated failure')
                else:
                    # Second call: succeed
                    return ProcessingResult(count=500, je_count=1500)
            
            mock_process.side_effect = fail_at_500
            
            result = orchestrator.execute_batch()
        
        # Should still succeed via recovery
        assert result.status == 'SUCCESS'
```

### Performance Test
```python
class TestBatchPerformance:
    """Performance tests for batch system"""
    
    def test_throughput_target(self):
        """Test batch meets throughput target"""
        
        # Create large dataset
        self.create_test_premiums(count=10000)
        
        start_time = time.time()
        
        orchestrator = BatchOrchestrator(
            batch_id='PERF-TEST',
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31)
        )
        
        result = orchestrator.execute_batch()
        
        elapsed = time.time() - start_time
        
        throughput = 10000 / elapsed
        
        # Should achieve at least 5,000 req/s
        assert throughput >= 5000, f'Throughput {throughput} below target'
    
    def test_scalability(self):
        """Test batch scales linearly"""
        
        results = {}
        
        for volume in [1000, 5000, 10000]:
            self.create_test_premiums(count=volume)
            
            start_time = time.time()
            orchestrator = BatchOrchestrator(
                batch_id=f'SCALE-{volume}',
                period_start=date(2025, 1, 1),
                period_end=date(2025, 1, 31)
            )
            result = orchestrator.execute_batch()
            elapsed = time.time() - start_time
            
            results[volume] = {
                'time': elapsed,
                'throughput': volume / elapsed
            }
        
        # Throughput should be consistent across volumes
        throughputs = [r['throughput'] for r in results.values()]
        avg_throughput = sum(throughputs) / len(throughputs)
        
        for throughput in throughputs:
            # Within 20% of average
            assert abs(throughput - avg_throughput) / avg_throughput < 0.2
```
### Dry Run Testing
```python
class DryRunManager:
    """Manage dry run execution"""
    
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.dry_run_id = f'{batch_id}-DRYRUN'
    
    def execute_dry_run(self) -> DryRunResult:
        """Execute dry run on staging database"""
        
        logger.info(f'Starting dry run for {self.batch_id}')
        
        # Step 1: Copy production data to staging
        self.copy_to_staging()
        
        # Step 2: Run batch on staging
        with override_settings(DATABASES={'default': STAGING_DB_CONFIG}):
            orchestrator = BatchOrchestrator(
                batch_id=self.dry_run_id,
                period_start=self.period_start,
                period_end=self.period_end
            )
            
            try:
                result = orchestrator.execute_batch()
                
                # Step 3: Validate results
                validation = self.validate_dry_run_results()
                
                # Step 4: Generate report
                report = self.generate_dry_run_report(result, validation)
                
                return DryRunResult(
                    status='SUCCESS',
                    timing=result.timing,
                    validation=validation,
                    report=report
                )
                
            except Exception as e:
                logger.error(f'Dry run failed: {e}', exc_info=True)
                return DryRunResult(
                    status='FAILED',
                    error=str(e)
                )
            
            finally:
                # Step 5: Clean up staging
                self.cleanup_staging()
    
    def generate_dry_run_report(self, result, validation) -> Dict:
        """Generate detailed dry run report"""
        
        return {
            'dry_run_id': self.dry_run_id,
            'executed_at': datetime.utcnow().isoformat(),
            'timing': {
                'total_time_minutes': result.timing.total_minutes,
                'target_time_minutes': 20,
                'buffer_remaining_minutes': 120 - result.timing.total_minutes,
                'projected_production_time': result.timing.total_minutes * 1.1  # Add 10% buffer
            },
            'throughput': {
                'transactions_per_second': result.throughput,
                'target_transactions_per_second': 5556,
                'meets_target': result.throughput >= 5556
            },
            'validation': {
                'record_count_match': validation.record_count_match,
                'sequence_integrity': validation.sequence_integrity,
                'debit_credit_balance': validation.debit_credit_balance,
                'fund_totals_match': validation.fund_totals_match
            },
            'recommendation': self.get_recommendation(result, validation)
        }
    
    def get_recommendation(self, result, validation) -> str:
        """Get recommendation based on dry run results"""
        
        if not validation.all_passed:
            return 'DO NOT PROCEED - Validation failures detected'
        
        if result.timing.total_minutes > 90:
            return 'WARNING - Batch may exceed 2-hour window. Consider optimization.'
        
        if result.throughput < 5556:
            return 'WARNING - Throughput below target. Monitor closely during production run.'
        
        return 'PROCEED - Dry run successful. System ready for production batch.'

# Usage: Run dry run 5 days before month-end
dry_run = DryRunManager('2025-01-MONTHEND')
result = dry_run.execute_dry_run()

if result.status == 'SUCCESS':
    print(f"Dry run completed in {result.timing.total_minutes} minutes")
    print(f"Recommendation: {result.report['recommendation']}")
else:
    print(f"Dry run failed: {result.error}")
```

#### Test Data generation 
```python
class TestDataGenerator:
    """Generate test data for batch testing"""
    
    def generate_premiums(self, count: int, batch_size: int = 1000):
        """Generate test premium transactions"""
        
        premiums = []
        
        for i in range(count):
            # Random premium amount between 500k and 5M
            premium_amount = Decimal(random.randint(500000, 5000000))
            
            # Pre-calculate fund allocations (40/40/20 split)
            fund_tabarru = (premium_amount * Decimal('0.40')).quantize(Decimal('0.01'))
            fund_tanahud = (premium_amount * Decimal('0.40')).quantize(Decimal('0.01'))
            fund_ujroh = premium_amount - fund_tabarru - fund_tanahud
            
            premium = PremiumTransaction(
                policy_id=random.randint(1, 1000),
                txn_date=date(2025, 1, random.randint(1, 31)),
                payment_date=date(2025, 1, random.randint(1, 31)),
                premium_amount=premium_amount,
                fund_tabarru=fund_tabarru,
                fund_tanahud=fund_tanahud,
                fund_ujroh=fund_ujroh,
                product_code='HYBRID-LIFE-001',
                plan_code='PLAN-A',
                payment_method='TRANSFER',
                status='PAID',
                batch_processed=False
            )
            
            premiums.append(premium)
            
            # Bulk insert in batches
            if len(premiums) >= batch_size:
                PremiumTransaction.objects.bulk_create(premiums)
                premiums = []
        
        # Insert remaining
        if premiums:
            PremiumTransaction.objects.bulk_create(premiums)
        
        logger.info(f'Generated {count} test premium transactions')
```

---

# 13. DEPLOYMENT PLAN

## 13.1 Deployment Phases

### Phase 1: Development Environment (Week 1-2)
```
Objectives:
- Deploy all components to dev environment
- Run unit and integration tests
- Validate basic functionality

Tasks:
├─ Setup dev database with test data
├─ Deploy batch orchestrator
├─ Deploy worker infrastructure (10 workers)
├─ Deploy RabbitMQ
├─ Setup monitoring (Prometheus + Grafana)
├─ Run test batch with 1k transactions
└─ Document any issues

Success Criteria:
✓ Batch completes successfully
✓ All validations pass
✓ Monitoring operational
✓ Zero critical issues

Duration: 2 weeks
```

### Phase 2: Staging Environment (Week 3-4)
```
Objectives:
- Deploy to staging with production-like data
- Performance testing
- Dry run validation

Tasks:
├─ Copy production data to staging
├─ Deploy all components
├─ Scale to 100 workers
├─ Run dry run with 10M transactions
├─ Measure performance metrics
├─ Stress test with 15M transactions
├─ Test failure scenarios
└─ Validate rollback procedures

Success Criteria:
✓ 10M batch completes in <20 minutes
✓ All validations pass
✓ Worker failure recovery works
✓ Rollback tested successfully
✓ Performance meets targets

Duration: 2 weeks
```

### Phase 3: Production Pilot (Week 5)
```
Objectives:
- Deploy to production
- Run pilot batch (off-cycle)
- Validate against manual process

Tasks:
├─ Deploy to production (off-hours)
├─ Run pilot batch with previous month data
├─ Compare results with manual month-end
├─ Financial team validation
├─ Audit review
└─ Document discrepancies (if any)

Success Criteria:
✓ Results match manual process 100%
✓ No data discrepancies
✓ Financial team sign-off
✓ Audit approval

Duration: 1 week
```

### Phase 4: Production Go-Live (Week 6)
```
Objectives:
- Execute first real month-end batch
- Monitor closely
- Validate results

Tasks:
├─ Pre-flight checks (Day -1)
├─ Dry run (Day -1)
├─ Execute real batch (Month-end night)
├─ Real-time monitoring
├─ Immediate validation
├─ Financial reporting
└─ Post-mortem review

Success Criteria:
✓ Batch completes within window
✓ All validations pass
✓ Reports ready for business open
✓ CFO sign-off

Duration: 1 week (+ ongoing monitoring)
```

## 13.2 Deployment Checklist

### Pre-Deployment Checklist
```
Infrastructure:
☐ Database resources upgraded (32→64 cores during window)
☐ Worker servers provisioned (10 servers, 16 cores each)
☐ RabbitMQ cluster deployed (3 nodes)
☐ Monitoring infrastructure ready (Prometheus, Grafana)
☐ Network connectivity validated (<1ms latency)
☐ Storage provisioned (2TB NVMe SSD)

Database:
☐ PostgreSQL 15+ installed
☐ Configuration tuned for batch processing
☐ Sequences created
☐ Batch functions deployed
☐ Tables created (staging, control, audit)
☐ Indexes created
☐ Backup configured

Application:
☐ Code deployed to all servers
☐ Dependencies installed
☐ Configuration files updated
☐ Environment variables set
☐ Celery workers configured
☐ Logging configured

Security:
☐ Access controls configured
☐ API authentication enabled
☐ Audit logging enabled
☐ Sensitive data masking verified
☐ Network security groups configured

Monitoring:
☐ Dashboard configured
☐ Alerts configured
☐ Email notifications setup
☐ Slack integration tested
☐ SMS alerts configured (critical only)

Documentation:
☐ Operations manual complete
☐ Runbook prepared
☐ Rollback procedures documented
☐ Contact list updated
☐ Training completed

Testing:
☐ Unit tests pass
☐ Integration tests pass
☐ Performance tests pass
☐ Dry run successful
☐ Failover tested

Sign-off:
☐ Engineering Lead
☐ Operations Manager
☐ DBA
☐ Security Team
☐ Finance Manager
☐ CFO
```

### Go-Live Checklist (Day of Month-End)
```
T-24 hours:
☐ Dry run executed successfully
☐ All validations passed
☐ Performance within targets
☐ Go/No-Go decision made

T-4 hours:
☐ Team assembled (ops, engineering, finance, DBA)
☐ Communication channels open (Slack, conference bridge)
☐ Monitoring dashboards up
☐ Database resources scaled up
☐ Workers standing by

T-30 minutes:
☐ Pre-flight checks executed
☐ All systems green
☐ Prerequisite batches confirmed complete
☐ Source data validated
☐ Final go/no-go decision

T-0 (Batch Start):
☐ Batch initiated
☐ Workers launched
☐ Monitoring active
☐ Team watching dashboards

During Batch:
☐ Progress monitored every 5 minutes
☐ Performance metrics tracked
☐ Worker status checked
☐ Alerts responded to

T+20 minutes (Expected Completion):
☐ All workers completed
☐ Validation passed
☐ Commit successful
☐ Source tables updated
☐ Fund balances updated

T+30 minutes:
☐ Reports generated
☐ Finance team notified
☐ CFO briefed
☐ Staging cleaned up
☐ Resources scaled down

T+60 minutes:
☐ Post-mortem started
☐ Metrics captured
☐ Issues documented
☐ Improvements identified
```

## 13.3 Rollback Plan
```
Rollback Decision Tree:

If Pre-Flight Fails:
├─ DO NOT START BATCH
├─ Investigate failure
├─ Fix issue
└─ Re-run pre-flight

If Worker Failures > 20%:
├─ PAUSE BATCH
├─ Investigate root cause
├─ Option A: Fix and resume
└─ Option B: Abort and reschedule

If Validation Fails:
├─ STOP BEFORE COMMIT
├─ Preserve staging data
├─ Investigate discrepancy
├─ DO NOT COMMIT to production
└─ Fix in staging, re-validate

If Post-Commit Issue Discovered:
├─ CRITICAL ALERT
├─ Assess impact
├─ Option A: Compensating entries
├─ Option B: Full rollback (extreme)
└─ CFO decision required

Rollback Execution (if needed):
1. Stop all workers (if running)
2. Execute rollback procedure
3. Verify production unchanged
4. Clean staging tables
5. Document cause
6. Schedule re-run
```

---

# 14. OPERATIONS MANUAL

## 14.1 Standard Operating Procedures

### SOP 1: Monthly Batch Execution
```
Title: Month-End Journal Entry Batch Processing
Frequency: Monthly (last day of month)
Duration: 20 minutes (with 100-minute buffer)
Responsibility: Operations Team

Prerequisites:
- AP/AR close completed
- Payroll processing completed
- All month-end adjustments finalized
- Finance team available for validation

Procedure:

Step 1: Pre-Batch Validation (Day -1, 5:00 PM)
1.1. Run dry run batch
    $ python manage.py execute_dry_run --batch-id=YYYY-MM-DRYRUN
1.2. Review dry run report
1.3. Confirm with Finance team
1.4. Document any concerns
1.5. Go/No-Go decision

Step 2: Pre-Flight Checks (Day 0, 10:30 PM)
2.1. Verify prerequisite batches complete
2.2. Check source data integrity
    $ python manage.py validate_source_data --period=YYYY-MM
2.3. Verify database resources
2.4. Test database write performance
2.5. Confirm monitoring operational
2.6. Team assembled (Ops, Engineering, Finance, DBA)

Step 3: Batch Initiation (Day 0, 11:00 PM)
3.1. Navigate to batch control interface
3.2. Click "Initiate Month-End Batch"
3.3. Enter period: YYYY-MM-01 to YYYY-MM-31
3.4. Worker count: 100
3.5. Dry run: No
3.6. Click "Start Batch"
3.7. Note batch ID

Step 4: Monitoring (11:00 PM - 11:20 PM)
4.1. Watch dashboard every 2 minutes
4.2. Monitor key metrics:
    - Throughput (target: >5,556 req/s)
    - Worker status (>90% running)
    - ETA (<20 minutes remaining)
    - Errors (0 validation errors)
4.3. Respond to alerts immediately
4.4. Document any issues

Step 5: Validation (11:20 PM - 11:23 PM)
5.1. Monitor validation phase
5.2. Review validation results
5.3. Verify all checks passed:
    ✓ Record count match
    ✓ Sequence integrity
    ✓ Debit/credit balance
    ✓ Fund totals
5.4. If any fail: STOP, investigate
5.5. If all pass: Proceed to commit

Step 6: Commit (11:23 PM - 11:27 PM)
6.1. System executes atomic commit
6.2. Monitor commit progress
6.3. Verify commit successful
6.4. Confirm all tables updated

Step 7: Post-Batch (11:27 PM - 11:40 PM)
7.1. Review completion summary
7.2. Download batch report
7.3. Notify Finance team
7.4. Generate CFO summary
7.5. Archive staging data
7.6. Scale down resources
7.7. Complete post-batch checklist

Step 8: Next Morning (Day 1, 8:00 AM)
8.1. Finance team validates reports
8.2. CFO reviews summary
8.3. Audit trail reviewed
8.4. Sign-off obtained
8.5. Archive batch logs

Escalation:
- Minor issues: Operations Lead
- Major issues: Engineering Lead + DBA
- Critical issues: CTO + CFO

Success Criteria:
✓ Batch completed in <20 minutes
✓ All validations passed
✓ Reports available at 8:00 AM
✓ CFO sign-off obtained
```

### SOP 2: Worker Failure Recovery
```
Title: Handle Worker Failure During Batch
Trigger: Worker status = FAILED or stalled >5 minutes

Procedure:

Step 1: Identify Failed Worker
1.1. Check worker status panel
1.2. Note worker ID
1.3. Check last checkpoint

Step 2: Assess Impact
2.1. How many workers failed? (<10%: OK, >20%: Critical)
2.2. Is batch falling behind schedule?
2.3. Review error logs

Step 3: Automatic Recovery (if <10% failed)
3.1. System auto-launches replacement worker
3.2. Replacement picks up from checkpoint
3.3. Monitor replacement progress
3.4. Document failure in log

Step 4: Manual Intervention (if >10% failed)
4.1. PAUSE batch if possible
4.2. Investigate root cause:
    - Database connection issue?
    - Memory issue?
    - Code bug?
4.3. Fix root cause
4.4. Resume or restart

Step 5: Document
5.1. Record failure details
5.2. Update incident log
5.3. Create post-mortem ticket
```

### SOP 3: Rollback Procedure
```
Title: Emergency Batch Rollback
Trigger: Critical validation failure or post-commit issue discovered

WARNING: This is an emergency procedure. Requires CFO approval.

Procedure:

Step 1: STOP EVERYTHING
1.1. Abort batch if running
1.2. Prevent any further commits
1.3. Assemble crisis team
1.4. Alert CFO

Step 2: Assess Situation
2.1. What went wrong?
2.2. Is data already committed?
2.3. What's the impact?
2.4. Can we fix without rollback?

Step 3: Decision Point
IF data NOT committed:
    - Clean staging tables
    - Investigate issue
    - Fix and re-run
    DONE

IF data committed:
    - Proceed to Step 4

Step 4: Execute Rollback (WITH CFO APPROVAL)
4.1. Take database backup
4.2. Execute rollback script:
    $ python manage.py rollback_batch --batch-id=YYYY-MM-MONTHEND --confirm
4.3. Verify:
    - Journal entries deleted
    - Fund balances reversed
    - Source transactions reset
4.4. Run integrity check

Step 5: Post-Rollback
5.1. Verify production state clean
5.2. Document what happened
5.3. Fix root cause
5.4. Schedule re-run
5.5. Notify all stakeholders

Step 6: Post-Mortem (Within 24 hours)
6.1. Root cause analysis
6.2. Document lessons learned
6.3. Update procedures
6.4. Implement preventive measures
```

## 14.2 Troubleshooting Guide
```
Common Issues and Solutions:

Issue: Batch throughput low (<4000 req/s)
Symptoms: Dashboard shows red throughput indicator, ETA > 30 minutes
Cause: Database contention or worker resource constraint
Solution:
1. Check database CPU/memory
2. Check worker CPU/memory
3. Consider adding workers dynamically
4. Check for slow queries

Issue: Multiple worker failures
Symptoms: >10 workers showing FAILED status
Cause: Database connection issues or code bug
Solution:
1. Check database connectivity
2. Check worker logs for common error
3. If database issue: wait for DB recovery
4. If code bug: abort batch, fix, re-run

Issue: Validation failure - record count mismatch
Symptoms: Pre-commit validation shows count mismatch
Cause: Worker lost records or source data changed
Solution:
1. DO NOT COMMIT
2. Compare expected vs actual
3. Check worker logs for errors
4. Verify source data unchanged
5. Re-run if necessary

Issue: Validation failure - debit/credit imbalance
Symptoms: Total debits ≠ total credits
Cause: Template logic error or data corruption
Solution:
1. CRITICAL - DO NOT COMMIT
2. Investigate specific entries causing imbalance
3. Check template logic
4. Verify fund calculations
5. Fix and re-run

Issue: Database connection lost mid-batch
Symptoms: Multiple workers reporting connection errors
Cause: Database restart or network issue
Solution:
1. Workers auto-retry with backoff
2. If persistent: PAUSE batch
3. Investigate database
4. Resume when fixed
5. Workers continue from checkpoints

Issue: Batch stuck at validation phase
Symptoms: Validation phase taking >10 minutes
Cause: Large dataset or database resource constraint
Solution:
1. Check database performance
2. Check if validation queries running
3. If hung: Consider timeout and abort
4. Investigate query performance

Issue: Out of disk space
Symptoms: Write errors, staging table insert failures
Cause: Insufficient disk space
Solution:
1. CRITICAL - STOP batch
2. Check disk usage
3. Clean old logs/archives
4. Increase disk if needed
5. Restart batch

Issue: CFO reports discrepancy next morning
Symptoms: Reports don't match expected values
Cause: Data issue or calculation error
Solution:
1. CRITICAL ESCALATION
2. Compare with source data
3. Re-run validation queries
4. If data is correct: explain discrepancy
5. If data is wrong: rollback may be required
6. CFO decision

Contact Information:
- Operations Team: ops@company.com (24/7 on-call)
- Engineering Lead: eng-lead@company.com
- DBA: dba@company.com (24/7 on-call)
- CFO: cfo@company.com (for critical issues)
- CTO: cto@company.com (for critical issues)

On-Call Schedule:
- Week 1: Alice (ops), Bob (engineering)
- Week 2: Carol (ops), Dave (engineering)
- Week 3: Eve (ops), Frank (engineering)
- Week 4: Grace (ops), Hank (engineering)
```

---

# 15. APPENDICES

## 15.1 Glossary
```
Batch ID: Unique identifier for month-end batch (e.g., "2025-01-MONTHEND")

Batch Window: 2-hour time period for month-end processing

Checkpoint: Progress snapshot saved every 1000 records for recovery

Dry Run: Test execution on staging data before production

Journal Entry (JE): Accounting record with debits and credits

Pre-Flight: Initial validation before batch execution

Sequence: Unique incrementing number for JE identification

Staging Table: Temporary table for batch processing

Throughput: Transactions processed per second (req/s)

Worker: Independent process handling subset of batch
```
