# Alert Rules Configuration
ALERT_RULES = {
    'performance': {
        'throughput_low': {
            'threshold': 4000,  # req/s
            'severity': 'WARNING',
            'message': 'Batch throughput below target',
            'action': 'Monitor closely, consider scaling',
            'notify': ['ops_team@company.com']
        },
        'throughput_critical': {
            'threshold': 2000,  # req/s
            'severity': 'CRITICAL',
            'message': 'Batch throughput critically low',
            'action': 'Immediate intervention required',
            'notify': ['ops_team@company.com', 'engineering_lead@company.com']
        },
        'eta_exceeded': {
            'threshold': 90,  # minutes
            'severity': 'CRITICAL',
            'message': 'Batch ETA exceeds 2-hour window',
            'action': 'Consider aborting and rescheduling',
            'notify': ['ops_team@company.com', 'cfo@company.com']
        }
    },
    'reliability': {
        'worker_failures': {
            'threshold': 10,  # failed workers
            'severity': 'WARNING',
            'message': 'Multiple worker failures detected',
            'action': 'Investigate worker logs',
            'notify': ['ops_team@company.com']
        },
        'validation_failure': {
            'threshold': 1,  # any failure
            'severity': 'CRITICAL',
            'message': 'Batch validation failed',
            'action': 'DO NOT COMMIT - investigate immediately',
            'notify': ['ops_team@company.com', 'finance_team@company.com']
        },
        'database_connection_lost': {
            'threshold': 1,
            'severity': 'CRITICAL',
            'message': 'Database connection lost',
            'action': 'Pause batch, investigate database',
            'notify': ['ops_team@company.com', 'dba@company.com']
        }
    },
    'business': {
        'batch_completion': {
            'severity': 'INFO',
            'message': 'Month-end batch completed successfully',
            'notify': ['finance_team@company.com', 'cfo@company.com']
        },
        'batch_failure': {
            'severity': 'CRITICAL',
            'message': 'Month-end batch failed',
            'action': 'Immediate escalation required',
            'notify': [
                'ops_team@company.com',
                'finance_team@company.com',
                'cfo@company.com',
                'cto@company.com'
            ]
        }
    }
}

class AlertManager:
    """Manage batch alerts and notifications"""
    
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.active_alerts = []
    
    def check_alerts(self):
        """Check all alert conditions"""
        
        # Performance alerts
        self.check_throughput_alerts()
        self.check_eta_alerts()
        
        # Reliability alerts
        self.check_worker_failure_alerts()
        self.check_validation_alerts()
        
        # Send notifications
        self.send_notifications()
    
    def check_throughput_alerts(self):
        """Check throughput against thresholds"""
        
        monitor = BatchMonitor(self.batch_id)
        throughput = monitor.get_throughput()
        current_rps = throughput['current_rps']
        
        if current_rps < ALERT_RULES['performance']['throughput_critical']['threshold']:
            self.create_alert(
                rule='throughput_critical',
                current_value=current_rps
            )
        elif current_rps < ALERT_RULES['performance']['throughput_low']['threshold']:
            self.create_alert(
                rule='throughput_low',
                current_value=current_rps
            )
    
    def send_notifications(self):
        """Send email/SMS notifications"""
        
        for alert in self.active_alerts:
            if not alert.notified:
                # Email notification
                self.send_email_alert(alert)
                
                # SMS notification for CRITICAL
                if alert.severity == 'CRITICAL':
                    self.send_sms_alert(alert)
                
                # Slack notification
                self.send_slack_alert(alert)
                
                alert.notified = True
                alert.save()
    
    def send_email_alert(self, alert: Alert):
        """Send email notification"""
        from django.core.mail import send_mail
        
        subject = f'[{alert.severity}] Batch Alert: {alert.message}'
        
        body = f"""
Batch Alert

Batch ID: {self.batch_id}
Severity: {alert.severity}
Time: {alert.created_at}

Alert: {alert.message}
Current Value: {alert.current_value}
Threshold: {alert.threshold}

Recommended Action: {alert.action}

Dashboard: https://batch.company.com/monitor/{self.batch_id}
        """
        
        send_mail(
            subject=subject,
            message=body,
            from_email='batch-alerts@company.com',
            recipient_list=alert.recipients,
            fail_silently=False
        )
    
    def send_slack_alert(self, alert: Alert):
        """Send Slack notification"""
        import requests
        
        webhook_url = settings.SLACK_WEBHOOK_URL
        
        color = {
            'INFO': '#36a64f',
            'WARNING': '#ff9900',
            'CRITICAL': '#ff0000'
        }[alert.severity]
        
        payload = {
            'attachments': [{
                'color': color,
                'title': f'{alert.severity}: {alert.message}',
                'fields': [
                    {'title': 'Batch ID', 'value': self.batch_id, 'short': True},
                    {'title': 'Current Value', 'value': str(alert.current_value), 'short': True},
                    {'title': 'Action', 'value': alert.action, 'short': False}
                ],
                'footer': 'Batch Monitoring System',
                'ts': int(alert.created_at.timestamp())
            }]
        }
        
        requests.post(webhook_url, json=payload)
