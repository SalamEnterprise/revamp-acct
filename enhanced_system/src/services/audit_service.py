"""
Comprehensive Audit Trail Service
Implements financial industry best practices for traceability
"""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field

from ..models.database import AuditLog, ApprovalWorkflow
from ..core.exceptions import AuditException, ComplianceException


class AuditEventType(str, Enum):
    """Audit event types for financial transactions"""
    # Journal Events
    JOURNAL_CREATED = "JOURNAL_CREATED"
    JOURNAL_MODIFIED = "JOURNAL_MODIFIED"
    JOURNAL_DELETED = "JOURNAL_DELETED"
    JOURNAL_APPROVED = "JOURNAL_APPROVED"
    JOURNAL_REJECTED = "JOURNAL_REJECTED"
    JOURNAL_POSTED = "JOURNAL_POSTED"
    JOURNAL_REVERSED = "JOURNAL_REVERSED"
    
    # Voucher Events
    VOUCHER_CREATED = "VOUCHER_CREATED"
    VOUCHER_EXPORTED = "VOUCHER_EXPORTED"
    VOUCHER_CANCELLED = "VOUCHER_CANCELLED"
    
    # Control Events
    PERIOD_OPENED = "PERIOD_OPENED"
    PERIOD_CLOSED = "PERIOD_CLOSED"
    PERIOD_LOCKED = "PERIOD_LOCKED"
    RECONCILIATION_PERFORMED = "RECONCILIATION_PERFORMED"
    
    # Security Events
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    
    # Compliance Events
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    FRAUD_ALERT = "FRAUD_ALERT"
    THRESHOLD_EXCEEDED = "THRESHOLD_EXCEEDED"


class AuditContext(BaseModel):
    """Context information for audit events"""
    user_id: int
    user_name: str
    user_role: str
    ip_address: str
    session_id: str
    device_info: Optional[str] = None
    location: Optional[str] = None
    authentication_method: str = "password"
    

class AuditEvent(BaseModel):
    """Comprehensive audit event with full traceability"""
    event_id: UUID = Field(default_factory=uuid4)
    event_type: AuditEventType
    event_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Entity information
    entity_type: str  # JOURNAL, VOUCHER, GL_ENTRY, etc.
    entity_id: str
    entity_description: Optional[str] = None
    
    # Context
    context: AuditContext
    
    # Change tracking
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changed_fields: List[str] = Field(default_factory=list)
    
    # Business context
    business_date: Optional[datetime] = None
    journal_type: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    
    # Compliance
    justification: Optional[str] = None
    approval_required: bool = False
    approval_chain: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_flags: List[str] = Field(default_factory=list)
    
    # Integrity
    hash_previous: Optional[str] = None
    hash_current: Optional[str] = None
    signature: Optional[str] = None
    
    # Risk scoring
    risk_score: float = 0.0
    anomaly_flags: List[str] = Field(default_factory=list)


class AuditTrailService:
    """
    Enterprise-grade audit trail service with:
    - Immutable logging
    - Hash chaining for integrity
    - Compliance checking
    - Fraud detection
    - Forensic capabilities
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._last_hash_cache = None
        
    async def log_event(
        self,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: str,
        context: AuditContext,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        justification: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> AuditEvent:
        """
        Log an audit event with full traceability
        
        This method:
        1. Creates immutable audit record
        2. Implements hash chaining
        3. Performs compliance checks
        4. Detects anomalies
        5. Triggers alerts if needed
        """
        
        # Create audit event
        event = AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            context=context,
            old_values=old_values,
            new_values=new_values,
            justification=justification
        )
        
        # Detect changed fields
        if old_values and new_values:
            event.changed_fields = self._detect_changes(old_values, new_values)
        
        # Add metadata
        if metadata:
            event.business_date = metadata.get('business_date')
            event.journal_type = metadata.get('journal_type')
            event.amount = metadata.get('amount')
            event.currency = metadata.get('currency')
        
        # Calculate risk score
        event.risk_score = await self._calculate_risk_score(event)
        
        # Check compliance
        compliance_result = await self._check_compliance(event)
        event.compliance_flags = compliance_result.get('flags', [])
        event.approval_required = compliance_result.get('approval_required', False)
        
        # Implement hash chaining for immutability
        event.hash_previous = await self._get_last_hash()
        event.hash_current = self._calculate_hash(event)
        
        # Store immutably
        await self._store_immutable(event)
        
        # Update cache
        self._last_hash_cache = event.hash_current
        
        # Trigger alerts if needed
        if event.risk_score > 0.7 or 'HIGH_RISK' in event.compliance_flags:
            await self._trigger_alert(event)
        
        # Real-time monitoring
        await self._send_to_monitoring(event)
        
        return event
    
    def _detect_changes(
        self,
        old_values: Dict,
        new_values: Dict
    ) -> List[str]:
        """Detect which fields changed"""
        changed = []
        
        all_keys = set(old_values.keys()) | set(new_values.keys())
        
        for key in all_keys:
            old_val = old_values.get(key)
            new_val = new_values.get(key)
            
            if old_val != new_val:
                changed.append(key)
        
        return changed
    
    async def _calculate_risk_score(self, event: AuditEvent) -> float:
        """
        Calculate risk score using multiple factors:
        - Time of activity (unusual hours)
        - Amount thresholds
        - User behavior patterns
        - Entity sensitivity
        """
        score = 0.0
        
        # Check unusual time
        hour = event.event_timestamp.hour
        if hour < 6 or hour > 22:  # Outside business hours
            score += 0.2
        
        # Check amount thresholds
        if event.amount:
            if event.amount > 1000000:  # High value
                score += 0.3
            elif event.amount > 10000000:  # Very high value
                score += 0.5
        
        # Check sensitive operations
        high_risk_events = [
            AuditEventType.JOURNAL_DELETED,
            AuditEventType.JOURNAL_REVERSED,
            AuditEventType.PERIOD_CLOSED,
            AuditEventType.FRAUD_ALERT
        ]
        
        if event.event_type in high_risk_events:
            score += 0.4
        
        # Check user patterns (simplified)
        if event.context.authentication_method != "password":
            score -= 0.1  # MFA reduces risk
        
        # Normalize score
        return min(max(score, 0.0), 1.0)
    
    async def _check_compliance(self, event: AuditEvent) -> Dict[str, Any]:
        """
        Check compliance rules:
        - Segregation of duties
        - Approval thresholds
        - Period controls
        - Regulatory requirements
        """
        flags = []
        approval_required = False
        
        # Check segregation of duties
        if event.event_type == AuditEventType.JOURNAL_APPROVED:
            if event.context.user_role not in ['SUPERVISOR', 'MANAGER']:
                flags.append('SEGREGATION_VIOLATION')
                raise ComplianceException("User not authorized to approve journals")
        
        # Check approval thresholds
        if event.amount and event.amount > 100000:
            approval_required = True
            if event.amount > 1000000:
                flags.append('HIGH_VALUE_TRANSACTION')
        
        # Check period controls
        if event.business_date:
            is_period_open = await self._check_period_open(event.business_date)
            if not is_period_open:
                flags.append('CLOSED_PERIOD_MODIFICATION')
                raise ComplianceException("Cannot modify closed period")
        
        # SOX compliance checks
        if event.event_type in [AuditEventType.JOURNAL_DELETED, AuditEventType.JOURNAL_MODIFIED]:
            if not event.justification:
                flags.append('SOX_JUSTIFICATION_MISSING')
                raise ComplianceException("Justification required for SOX compliance")
        
        return {
            'flags': flags,
            'approval_required': approval_required
        }
    
    async def _check_period_open(self, business_date: datetime) -> bool:
        """Check if period is open for posting"""
        # Query period control table
        # For now, simplified implementation
        current_date = datetime.utcnow().date()
        business_date_only = business_date.date()
        
        # Allow current month and previous month
        if (current_date.year == business_date_only.year and 
            current_date.month - business_date_only.month <= 1):
            return True
        
        return False
    
    def _calculate_hash(self, event: AuditEvent) -> str:
        """Calculate SHA256 hash of event for integrity"""
        # Create deterministic string representation
        event_data = {
            'event_id': str(event.event_id),
            'event_type': event.event_type,
            'event_timestamp': event.event_timestamp.isoformat(),
            'entity_type': event.entity_type,
            'entity_id': event.entity_id,
            'context_user_id': event.context.user_id,
            'old_values': event.old_values,
            'new_values': event.new_values,
            'hash_previous': event.hash_previous
        }
        
        # Convert to JSON with sorted keys for consistency
        event_json = json.dumps(event_data, sort_keys=True, default=str)
        
        # Calculate SHA256
        return hashlib.sha256(event_json.encode()).hexdigest()
    
    async def _get_last_hash(self) -> str:
        """Get hash of last audit event for chaining"""
        if self._last_hash_cache:
            return self._last_hash_cache
        
        # Query database for last event
        query = select(AuditLog).order_by(AuditLog.event_timestamp.desc()).limit(1)
        result = await self.db.execute(query)
        last_event = result.scalar_one_or_none()
        
        if last_event:
            return last_event.hash_current
        
        # Genesis hash
        return "0" * 64
    
    async def _store_immutable(self, event: AuditEvent) -> None:
        """Store event in immutable audit log"""
        
        # Convert to database model
        audit_log = AuditLog(
            event_id=str(event.event_id),
            event_type=event.event_type,
            event_timestamp=event.event_timestamp,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            user_id=event.context.user_id,
            user_name=event.context.user_name,
            user_role=event.context.user_role,
            ip_address=event.context.ip_address,
            session_id=event.context.session_id,
            old_values=event.old_values,
            new_values=event.new_values,
            changed_fields=event.changed_fields,
            business_date=event.business_date,
            amount=event.amount,
            justification=event.justification,
            approval_required=event.approval_required,
            compliance_flags=event.compliance_flags,
            risk_score=event.risk_score,
            hash_previous=event.hash_previous,
            hash_current=event.hash_current
        )
        
        self.db.add(audit_log)
        await self.db.commit()
        
        # Replicate to backup/archive
        await self._replicate_to_archive(event)
    
    async def _replicate_to_archive(self, event: AuditEvent) -> None:
        """Replicate to archive for long-term storage"""
        # Implementation would send to:
        # - Cold storage
        # - Compliance archive
        # - Blockchain if implemented
        pass
    
    async def _trigger_alert(self, event: AuditEvent) -> None:
        """Trigger alerts for high-risk events"""
        # Send to:
        # - Security team
        # - Compliance officer
        # - Risk management
        # - Real-time monitoring dashboard
        pass
    
    async def _send_to_monitoring(self, event: AuditEvent) -> None:
        """Send to real-time monitoring systems"""
        # Push to:
        # - Prometheus metrics
        # - Grafana dashboards
        # - SIEM system
        # - Compliance dashboard
        pass
    
    async def verify_integrity(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Verify audit trail integrity using hash chain
        Returns integrity report
        """
        
        # Query events in range
        query = select(AuditLog).where(
            and_(
                AuditLog.event_timestamp >= start_date,
                AuditLog.event_timestamp <= end_date
            )
        ).order_by(AuditLog.event_timestamp)
        
        result = await self.db.execute(query)
        events = result.scalars().all()
        
        # Verify hash chain
        errors = []
        previous_hash = None
        
        for event in events:
            # Check hash chain
            if previous_hash and event.hash_previous != previous_hash:
                errors.append({
                    'event_id': event.event_id,
                    'error': 'Hash chain broken',
                    'expected': previous_hash,
                    'actual': event.hash_previous
                })
            
            # Recalculate hash
            calculated_hash = self._recalculate_hash(event)
            if calculated_hash != event.hash_current:
                errors.append({
                    'event_id': event.event_id,
                    'error': 'Hash mismatch',
                    'expected': calculated_hash,
                    'actual': event.hash_current
                })
            
            previous_hash = event.hash_current
        
        return {
            'period': f"{start_date} to {end_date}",
            'events_checked': len(events),
            'errors_found': len(errors),
            'integrity': len(errors) == 0,
            'errors': errors
        }
    
    def _recalculate_hash(self, event) -> str:
        """Recalculate hash for verification"""
        event_data = {
            'event_id': event.event_id,
            'event_type': event.event_type,
            'event_timestamp': event.event_timestamp.isoformat(),
            'entity_type': event.entity_type,
            'entity_id': event.entity_id,
            'user_id': event.user_id,
            'old_values': event.old_values,
            'new_values': event.new_values,
            'hash_previous': event.hash_previous
        }
        
        event_json = json.dumps(event_data, sort_keys=True, default=str)
        return hashlib.sha256(event_json.encode()).hexdigest()
    
    async def forensic_search(
        self,
        entity_id: Optional[str] = None,
        user_id: Optional[int] = None,
        event_type: Optional[AuditEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ip_address: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Forensic search capability for investigations
        """
        
        query = select(AuditLog)
        
        # Build filter conditions
        conditions = []
        
        if entity_id:
            conditions.append(AuditLog.entity_id == entity_id)
        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if event_type:
            conditions.append(AuditLog.event_type == event_type)
        if start_date:
            conditions.append(AuditLog.event_timestamp >= start_date)
        if end_date:
            conditions.append(AuditLog.event_timestamp <= end_date)
        if ip_address:
            conditions.append(AuditLog.ip_address == ip_address)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(AuditLog.event_timestamp.desc())
        
        result = await self.db.execute(query)
        events = result.scalars().all()
        
        # Format for forensic report
        return [
            {
                'event_id': e.event_id,
                'timestamp': e.event_timestamp,
                'event_type': e.event_type,
                'entity': f"{e.entity_type}:{e.entity_id}",
                'user': f"{e.user_name} ({e.user_id})",
                'ip_address': e.ip_address,
                'changes': e.changed_fields,
                'risk_score': e.risk_score,
                'compliance_flags': e.compliance_flags,
                'hash': e.hash_current
            }
            for e in events
        ]