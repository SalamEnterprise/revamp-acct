# Django View for Dashboard
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

class BatchMonitorDashboard(TemplateView):
    """Real-time batch monitoring dashboard"""
    
    template_name = 'batch/monitor_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch_id = self.kwargs.get('batch_id')
        
        context['batch_id'] = batch_id
        context['refresh_interval'] = 5  # seconds
        
        return context

# API endpoint for dashboard data (called every 5 seconds)
class BatchMonitorAPI(View):
    """API for real-time batch monitoring data"""
    
    def get(self, request, batch_id):
        """Get current batch status"""
        
        try:
            monitor = BatchMonitor(batch_id)
            data = monitor.get_dashboard_data()
            
            return JsonResponse(data)
            
        except BatchNotFound:
            return JsonResponse(
                {'error': 'Batch not found'},
                status=404
            )

class BatchMonitor:
    """Monitor batch execution"""
    
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.master = StagingMonthEndMaster.objects.get(batch_id=batch_id)
        
    def get_dashboard_data(self) -> Dict:
        """Collect all dashboard metrics"""
        
        return {
            'batch_info': self.get_batch_info(),
            'progress': self.get_progress(),
            'throughput': self.get_throughput(),
            'workers': self.get_worker_status(),
            'performance': self.get_performance_metrics(),
            'database': self.get_database_metrics(),
            'validation': self.get_validation_status(),
            'resources': self.get_resource_usage(),
            'events': self.get_recent_events(),
            'alerts': self.get_active_alerts()
        }
    
    def get_progress(self) -> Dict:
        """Calculate overall progress"""
        
        # Get worker progress
        workers = BatchWorkerControl.objects.filter(batch_id=self.batch_id)
        
        total_records = sum(w.expected_record_count for w in workers)
        processed_records = sum(w.records_processed for w in workers)
        
        percentage = (processed_records / total_records * 100) if total_records > 0 else 0
        
        # Calculate ETA
        elapsed = (datetime.utcnow() - self.master.processing_started_at).total_seconds()
        rate = processed_records / elapsed if elapsed > 0 else 0
        remaining_records = total_records - processed_records
        eta_seconds = remaining_records / rate if rate > 0 else 0
        
        return {
            'total_records': total_records,
            'processed_records': processed_records,
            'percentage': round(percentage, 1),
            'elapsed_seconds': int(elapsed),
            'elapsed_formatted': format_duration(elapsed),
            'eta_seconds': int(eta_seconds),
            'eta_formatted': format_duration(eta_seconds),
            'estimated_completion': (
                datetime.utcnow() + timedelta(seconds=eta_seconds)
            ).isoformat()
        }
    
    def get_throughput(self) -> Dict:
        """Calculate throughput metrics"""
        
        # Get recent checkpoints (last 60 seconds)
        recent_checkpoints = BatchProcessingCheckpoint.objects.filter(
            batch_id=self.batch_id,
            checkpoint_at__gte=datetime.utcnow() - timedelta(seconds=60)
        )
        
        if recent_checkpoints.exists():
            current_rps = recent_checkpoints.aggregate(
                Avg('records_per_second')
            )['records_per_second__avg']
        else:
            current_rps = 0
        
        # Average throughput
        elapsed = (datetime.utcnow() - self.master.processing_started_at).total_seconds()
        workers = BatchWorkerControl.objects.filter(batch_id=self.batch_id)
        total_processed = sum(w.records_processed for w in workers)
        average_rps = total_processed / elapsed if elapsed > 0 else 0
        
        # Peak throughput
        peak_checkpoint = BatchProcessingCheckpoint.objects.filter(
            batch_id=self.batch_id
        ).order_by('-records_per_second').first()
        
        peak_rps = peak_checkpoint.records_per_second if peak_checkpoint else 0
        
        return {
            'current_rps': round(current_rps, 0),
            'average_rps': round(average_rps, 0),
            'peak_rps': round(peak_rps, 0),
            'target_rps': 5556,
            'performance_ratio': round(current_rps / 5556, 2),
            'status': 'good' if current_rps > 5556 else 'warning'
        }
    
    def get_worker_status(self) -> Dict:
        """Get worker status summary"""
        
        workers = BatchWorkerControl.objects.filter(batch_id=self.batch_id)
        
        status_counts = workers.values('status').annotate(
            count=Count('worker_id')
        )
        
        status_dict = {item['status']: item['count'] for item in status_counts}
        
        # Identify slow workers (< 500 req/s)
        slow_workers = workers.filter(
            status='RUNNING',
            records_per_second__lt=500
        ).values_list('worker_id', flat=True)
        
        return {
            'total': workers.count(),
            'running': status_dict.get('RUNNING', 0),
            'completed': status_dict.get('COMPLETED', 0),
            'failed': status_dict.get('FAILED', 0),
            'slow_count': len(slow_workers),
            'slow_workers': list(slow_workers)
        }
    
    def get_database_metrics(self) -> Dict:
        """Get database performance metrics"""
        
        with connection.cursor() as cursor:
            # Active connections
            cursor.execute("""
                SELECT COUNT(*) 
                FROM pg_stat_activity 
                WHERE datname = current_database()
                  AND state = 'active'
            """)
            active_connections = cursor.fetchone()[0]
            
            # Cache hit rate
            cursor.execute("""
                SELECT 
                    sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100 
                    as cache_hit_rate
                FROM pg_statio_user_tables
            """)
            cache_hit_rate = cursor.fetchone()[0] or 0
            
            # Average query time
            cursor.execute("""
                SELECT AVG(mean_exec_time) 
                FROM pg_stat_statements 
                WHERE queryid IS NOT NULL
            """)
            avg_query_time = cursor.fetchone()[0] or 0
        
        return {
            'active_connections': active_connections,
            'max_connections': 250,
            'utilization_pct': round(active_connections / 250 * 100, 1),
            'cache_hit_rate': round(cache_hit_rate, 1),
            'avg_query_time_ms': round(avg_query_time, 1)
        }
