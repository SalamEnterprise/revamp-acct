class WorkerRecoveryManager:
    """Manage worker failures and recovery"""
    
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
    
    def detect_failed_workers(self) -> List[int]:
        """Detect workers that have failed or stalled"""
        
        # Find workers with no checkpoint in last 5 minutes
        stalled_threshold = datetime.utcnow() - timedelta(minutes=5)
        
        stalled_workers = BatchWorkerControl.objects.filter(
            batch_id=self.batch_id,
            status='RUNNING',
            last_checkpoint_at__lt=stalled_threshold
        )
        
        # Find workers marked as failed
        failed_workers = BatchWorkerControl.objects.filter(
            batch_id=self.batch_id,
            status='FAILED'
        )
        
        return list(stalled_workers.values_list('worker_id', flat=True)) + \
               list(failed_workers.values_list('worker_id', flat=True))
    
    def recover_worker(self, worker_id: int) -> bool:
        """Attempt to recover a failed worker"""
        
        try:
            worker_control = BatchWorkerControl.objects.get(
                batch_id=self.batch_id,
                worker_id=worker_id
            )
            
            # Get last checkpoint
            last_checkpoint = BatchProcessingCheckpoint.objects.filter(
                batch_id=self.batch_id,
                worker_id=worker_id
            ).order_by('-checkpoint_at').first()
            
            if not last_checkpoint:
                # No checkpoint yet, restart from beginning
                resume_from = 0
            else:
                # Resume from last checkpoint
                resume_from = last_checkpoint.records_processed
            
            # Mark original worker as permanently failed
            worker_control.status = 'FAILED'
            worker_control.save()
            
            # Launch replacement worker
            self.launch_replacement_worker(
                original_worker_id=worker_id,
                resume_from=resume_from,
                sequence_range=(
                    worker_control.sequence_start,
                    worker_control.sequence_end
                )
            )
            
            logger.info(
                f'Worker {worker_id} recovery initiated. '
                f'Resuming from record {resume_from}'
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f'Failed to recover worker {worker_id}: {e}',
                exc_info=True
            )
            return False
    
    def launch_replacement_worker(
        self,
        original_worker_id: int,
        resume_from: int,
        sequence_range: Tuple[int, int]
    ):
        """Launch replacement worker for failed worker"""
        
        # Assign new worker ID (100 + original_id for tracking)
        new_worker_id = 100 + original_worker_id
        
        # Create control record for replacement
        BatchWorkerControl.objects.create(
            worker_id=new_worker_id,
            batch_id=self.batch_id,
            sequence_start=sequence_range[0],
            sequence_end=sequence_range[1],
            status='ASSIGNED',
            # Note: replacement worker takes over sequence range
        )
        
        # Launch Celery task
        from .tasks import process_batch_worker
        
        process_batch_worker.delay(
            batch_id=self.batch_id,
            worker_id=new_worker_id,
            sequence_start=sequence_range[0],
            sequence_end=sequence_range[1],
            resume_from=resume_from  # Skip already processed records
        )
