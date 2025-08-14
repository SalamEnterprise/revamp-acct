"""
Financial Compliance and Control Service
Implements industry best practices for journal processing
"""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from ..models.domain import JournalEntry, JournalStatus, Money
from ..models.database import SunJournal, PostingPeriod, ApprovalWorkflow
from ..core.exceptions import ComplianceException, ValidationError
from .audit_service import AuditTrailService, AuditEventType, AuditContext


class PeriodStatus(str, Enum):
    """Posting period status"""
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"  # Permanently locked for audit


class ApprovalStatus(str, Enum):
    """Approval workflow status"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class ComplianceRule(str, Enum):
    """Compliance rules for validation"""
    BALANCED_ENTRY = "BALANCED_ENTRY"
    VALID_PERIOD = "VALID_PERIOD"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    SEGREGATION_OF_DUTIES = "SEGREGATION_OF_DUTIES"
    DUPLICATE_CHECK = "DUPLICATE_CHECK"
    THRESHOLD_CHECK = "THRESHOLD_CHECK"
    FRAUD_DETECTION = "FRAUD_DETECTION"
    TAX_COMPLIANCE = "TAX_COMPLIANCE"
    IFRS_COMPLIANCE = "IFRS_COMPLIANCE"
    SOX_COMPLIANCE = "SOX_COMPLIANCE"


class ComplianceService:
    """
    Comprehensive compliance service implementing:
    - Period controls
    - Approval workflows
    - Segregation of duties
    - Fraud detection
    - Regulatory compliance (SOX, IFRS, etc.)
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        audit_service: AuditTrailService
    ):
        self.db = db_session
        self.audit = audit_service
        
        # Thresholds (should be configurable)
        self.APPROVAL_THRESHOLD_LEVEL_1 = Decimal("100000")
        self.APPROVAL_THRESHOLD_LEVEL_2 = Decimal("1000000")
        self.APPROVAL_THRESHOLD_LEVEL_3 = Decimal("10000000")
    
    # ========================================
    # PERIOD CONTROL
    # ========================================
    
    async def open_period(
        self,
        period_date: date,
        context: AuditContext
    ) -> Dict[str, Any]:
        """Open a posting period"""
        
        # Check authorization
        if context.user_role not in ['MANAGER', 'ADMIN']:
            raise ComplianceException("Unauthorized to open periods")
        
        # Check if period exists
        existing = await self._get_period(period_date)
        if existing and existing.status != PeriodStatus.CLOSED:
            raise ComplianceException(f"Period {period_date} is already {existing.status}")
        
        # Create or update period
        period = PostingPeriod(
            period_date=period_date,
            status=PeriodStatus.OPEN,
            opened_by=context.user_id,
            opened_date=datetime.utcnow()
        )
        
        self.db.add(period)
        await self.db.commit()
        
        # Audit log
        await self.audit.log_event(
            event_type=AuditEventType.PERIOD_OPENED,
            entity_type="PERIOD",
            entity_id=str(period_date),
            context=context,
            new_values={'status': PeriodStatus.OPEN}
        )
        
        return {
            'period': period_date,
            'status': PeriodStatus.OPEN,
            'opened_by': context.user_name,
            'opened_at': datetime.utcnow()
        }
    
    async def close_period(
        self,
        period_date: date,
        context: AuditContext,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Close a posting period with validations
        """
        
        # Check authorization
        if context.user_role not in ['MANAGER', 'CFO', 'ADMIN']:
            raise ComplianceException("Unauthorized to close periods")
        
        # Get period
        period = await self._get_period(period_date)
        if not period or period.status != PeriodStatus.OPEN:
            raise ComplianceException(f"Period {period_date} is not open")
        
        # Run closing validations
        validation_results = await self._validate_period_closing(period_date)
        
        if not validation_results['can_close'] and not force:
            raise ComplianceException(
                f"Period cannot be closed: {validation_results['issues']}"
            )
        
        # Update period status
        period.status = PeriodStatus.CLOSING
        period.closing_started_by = context.user_id
        period.closing_started_date = datetime.utcnow()
        
        # Run closing procedures
        closing_results = await self._run_closing_procedures(period_date)
        
        # Final close
        period.status = PeriodStatus.CLOSED
        period.closed_by = context.user_id
        period.closed_date = datetime.utcnow()
        
        await self.db.commit()
        
        # Audit log
        await self.audit.log_event(
            event_type=AuditEventType.PERIOD_CLOSED,
            entity_type="PERIOD",
            entity_id=str(period_date),
            context=context,
            old_values={'status': PeriodStatus.OPEN},
            new_values={'status': PeriodStatus.CLOSED},
            metadata={'closing_results': closing_results}
        )
        
        return {
            'period': period_date,
            'status': PeriodStatus.CLOSED,
            'closed_by': context.user_name,
            'closed_at': datetime.utcnow(),
            'validation_results': validation_results,
            'closing_results': closing_results
        }
    
    async def _validate_period_closing(self, period_date: date) -> Dict[str, Any]:
        """Validate if period can be closed"""
        
        issues = []
        warnings = []
        
        # Check for unposted journals
        unposted_count = await self.db.scalar(
            select(func.count()).select_from(SunJournal).where(
                and_(
                    SunJournal.journal_date == period_date,
                    SunJournal.voucher_id.is_(None)
                )
            )
        )
        
        if unposted_count > 0:
            issues.append(f"{unposted_count} unposted journals")
        
        # Check for unapproved high-value transactions
        unapproved = await self._check_unapproved_transactions(period_date)
        if unapproved:
            issues.append(f"{len(unapproved)} unapproved high-value transactions")
        
        # Check trial balance
        trial_balance = await self._check_trial_balance(period_date)
        if not trial_balance['balanced']:
            issues.append(f"Trial balance not balanced: {trial_balance['difference']}")
        
        # Check reconciliation status
        recon_status = await self._check_reconciliation_status(period_date)
        if not recon_status['complete']:
            warnings.append(f"Reconciliation incomplete: {recon_status['pending_items']}")
        
        return {
            'can_close': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'trial_balance': trial_balance,
            'reconciliation': recon_status
        }
    
    async def _run_closing_procedures(self, period_date: date) -> Dict[str, Any]:
        """Run period closing procedures"""
        
        results = {}
        
        # 1. Create closing journal entries (accruals, deferrals, etc.)
        results['closing_entries'] = await self._create_closing_entries(period_date)
        
        # 2. Calculate period P&L
        results['period_pl'] = await self._calculate_period_pl(period_date)
        
        # 3. Update balance sheet
        results['balance_sheet'] = await self._update_balance_sheet(period_date)
        
        # 4. Generate compliance reports
        results['compliance_reports'] = await self._generate_compliance_reports(period_date)
        
        return results
    
    # ========================================
    # APPROVAL WORKFLOW
    # ========================================
    
    async def submit_for_approval(
        self,
        journal: JournalEntry,
        context: AuditContext,
        urgency: str = "NORMAL"
    ) -> Dict[str, Any]:
        """Submit journal for approval based on thresholds"""
        
        # Determine approval level required
        approval_level = self._determine_approval_level(journal.total_amount)
        
        if approval_level == 0:
            # Auto-approve small amounts
            return await self._auto_approve(journal, context)
        
        # Get approvers for level
        approvers = await self._get_approvers(approval_level, journal.journal_type)
        
        # Create approval workflow
        workflow = ApprovalWorkflow(
            entity_type="JOURNAL",
            entity_id=str(journal.id),
            amount=journal.total_amount.amount,
            approval_level=approval_level,
            submitted_by=context.user_id,
            submitted_date=datetime.utcnow(),
            status=ApprovalStatus.PENDING,
            approvers=approvers,
            urgency=urgency,
            sla_hours=24 if urgency == "URGENT" else 72
        )
        
        self.db.add(workflow)
        await self.db.commit()
        
        # Send notifications
        await self._notify_approvers(workflow, journal)
        
        # Audit log
        await self.audit.log_event(
            event_type=AuditEventType.JOURNAL_CREATED,
            entity_type="JOURNAL",
            entity_id=str(journal.id),
            context=context,
            metadata={
                'amount': journal.total_amount.amount,
                'approval_required': True,
                'approval_level': approval_level
            }
        )
        
        return {
            'workflow_id': workflow.id,
            'status': ApprovalStatus.PENDING,
            'approval_level': approval_level,
            'approvers': approvers,
            'sla': workflow.sla_hours
        }
    
    def _determine_approval_level(self, amount: Money) -> int:
        """Determine approval level based on amount"""
        
        if amount.amount <= self.APPROVAL_THRESHOLD_LEVEL_1:
            return 0  # No approval needed
        elif amount.amount <= self.APPROVAL_THRESHOLD_LEVEL_2:
            return 1  # Level 1 approval
        elif amount.amount <= self.APPROVAL_THRESHOLD_LEVEL_3:
            return 2  # Level 2 approval
        else:
            return 3  # Level 3 (CFO) approval
    
    async def approve_journal(
        self,
        journal_id: UUID,
        context: AuditContext,
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        """Approve a journal entry"""
        
        # Get workflow
        workflow = await self._get_workflow(journal_id)
        if not workflow:
            raise ValidationError("No approval workflow found")
        
        # Check authorization
        if context.user_id not in workflow.approvers:
            raise ComplianceException("User not authorized to approve this journal")
        
        # Check segregation of duties
        if workflow.submitted_by == context.user_id:
            raise ComplianceException("Cannot approve own submission (segregation of duties)")
        
        # Update workflow
        workflow.status = ApprovalStatus.APPROVED
        workflow.approved_by = context.user_id
        workflow.approved_date = datetime.utcnow()
        workflow.approval_comments = comments
        
        # Update journal status
        await self._update_journal_status(journal_id, JournalStatus.VALIDATED)
        
        await self.db.commit()
        
        # Audit log
        await self.audit.log_event(
            event_type=AuditEventType.JOURNAL_APPROVED,
            entity_type="JOURNAL",
            entity_id=str(journal_id),
            context=context,
            metadata={'comments': comments}
        )
        
        return {
            'journal_id': journal_id,
            'status': ApprovalStatus.APPROVED,
            'approved_by': context.user_name,
            'approved_at': datetime.utcnow()
        }
    
    # ========================================
    # FRAUD DETECTION
    # ========================================
    
    async def detect_fraud_indicators(
        self,
        journal: JournalEntry
    ) -> Dict[str, Any]:
        """
        Detect potential fraud indicators using multiple techniques:
        - Benford's Law
        - Duplicate detection
        - Round number analysis
        - Time pattern analysis
        - Unusual combinations
        """
        
        indicators = []
        risk_score = 0.0
        
        # 1. Benford's Law Analysis
        benford_result = self._benford_analysis(journal)
        if benford_result['deviation'] > 0.15:
            indicators.append("BENFORD_DEVIATION")
            risk_score += 0.3
        
        # 2. Check for duplicates
        duplicate_check = await self._check_duplicates(journal)
        if duplicate_check['has_duplicates']:
            indicators.append("DUPLICATE_DETECTED")
            risk_score += 0.4
        
        # 3. Round number analysis
        round_analysis = self._analyze_round_numbers(journal)
        if round_analysis['suspicious']:
            indicators.append("EXCESSIVE_ROUND_NUMBERS")
            risk_score += 0.2
        
        # 4. Time pattern analysis
        time_analysis = self._analyze_time_patterns(journal)
        if time_analysis['unusual']:
            indicators.append("UNUSUAL_TIME_PATTERN")
            risk_score += 0.2
        
        # 5. Check unusual account combinations
        combo_check = await self._check_unusual_combinations(journal)
        if combo_check['suspicious']:
            indicators.append("UNUSUAL_ACCOUNT_COMBINATION")
            risk_score += 0.3
        
        # 6. Check for split transactions (structuring)
        split_check = await self._check_split_transactions(journal)
        if split_check['potential_structuring']:
            indicators.append("POTENTIAL_STRUCTURING")
            risk_score += 0.5
        
        # Normalize risk score
        risk_score = min(risk_score, 1.0)
        
        return {
            'risk_score': risk_score,
            'indicators': indicators,
            'details': {
                'benford': benford_result,
                'duplicates': duplicate_check,
                'round_numbers': round_analysis,
                'time_patterns': time_analysis,
                'combinations': combo_check,
                'structuring': split_check
            },
            'requires_review': risk_score > 0.5
        }
    
    def _benford_analysis(self, journal: JournalEntry) -> Dict[str, Any]:
        """Apply Benford's Law to detect anomalies"""
        
        # Extract first digits from amounts
        first_digits = []
        for line in journal.lines:
            amount_str = str(line.amount.amount)
            if amount_str[0].isdigit() and amount_str[0] != '0':
                first_digits.append(int(amount_str[0]))
        
        if len(first_digits) < 10:
            return {'deviation': 0, 'sample_size': len(first_digits)}
        
        # Expected Benford distribution
        benford_expected = {
            1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097,
            5: 0.079, 6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046
        }
        
        # Calculate actual distribution
        actual_dist = {i: first_digits.count(i) / len(first_digits) for i in range(1, 10)}
        
        # Calculate deviation
        deviation = sum(
            abs(actual_dist.get(i, 0) - expected)
            for i, expected in benford_expected.items()
        ) / 9
        
        return {
            'deviation': deviation,
            'sample_size': len(first_digits),
            'distribution': actual_dist
        }
    
    def _analyze_round_numbers(self, journal: JournalEntry) -> Dict[str, Any]:
        """Check for excessive round numbers (potential manipulation)"""
        
        round_count = 0
        total_count = len(journal.lines)
        
        for line in journal.lines:
            # Check if amount is round (ends in 00)
            if line.amount.amount % 100 == 0:
                round_count += 1
        
        round_percentage = round_count / total_count if total_count > 0 else 0
        
        # Suspicious if more than 30% are round numbers
        return {
            'suspicious': round_percentage > 0.3,
            'round_percentage': round_percentage,
            'round_count': round_count,
            'total_count': total_count
        }
    
    def _analyze_time_patterns(self, journal: JournalEntry) -> Dict[str, Any]:
        """Analyze time patterns for unusual activity"""
        
        creation_hour = journal.created_at.hour
        creation_day = journal.created_at.weekday()
        
        unusual_indicators = []
        
        # Check for after-hours activity
        if creation_hour < 6 or creation_hour > 20:
            unusual_indicators.append("AFTER_HOURS")
        
        # Check for weekend activity
        if creation_day >= 5:  # Saturday = 5, Sunday = 6
            unusual_indicators.append("WEEKEND")
        
        # Check for end-of-period activity
        if journal.journal_date.day >= 28:
            unusual_indicators.append("PERIOD_END")
        
        return {
            'unusual': len(unusual_indicators) > 0,
            'indicators': unusual_indicators,
            'creation_time': journal.created_at
        }
    
    async def _check_duplicates(self, journal: JournalEntry) -> Dict[str, Any]:
        """Check for duplicate transactions"""
        
        # Build signature for duplicate detection
        signature_parts = []
        for line in journal.lines:
            signature_parts.append(
                f"{line.account_code}:{line.amount.amount}:{line.dc_marker}"
            )
        signature = "|".join(sorted(signature_parts))
        
        # Check for similar journals in the last 30 days
        date_from = journal.journal_date - timedelta(days=30)
        
        similar = await self.db.execute(
            select(SunJournal).where(
                and_(
                    SunJournal.journal_date >= date_from,
                    SunJournal.journal_date <= journal.journal_date,
                    SunJournal.id != str(journal.id)
                )
            )
        )
        
        duplicates = []
        for existing in similar.scalars():
            # Compare signatures (simplified)
            if self._journals_similar(journal, existing):
                duplicates.append(existing.id)
        
        return {
            'has_duplicates': len(duplicates) > 0,
            'duplicate_ids': duplicates,
            'signature': signature
        }
    
    def _journals_similar(self, journal1: JournalEntry, existing: Any) -> bool:
        """Check if two journals are similar (potential duplicates)"""
        # Simplified comparison - in production would be more sophisticated
        return False  # Placeholder
    
    async def _check_unusual_combinations(self, journal: JournalEntry) -> Dict[str, Any]:
        """Check for unusual account combinations"""
        
        suspicious_combinations = []
        
        # Example suspicious patterns
        for line in journal.lines:
            # Cash to expense without approval
            if "CASH" in line.account_code and line.dc_marker == "C":
                for other_line in journal.lines:
                    if "EXPENSE" in other_line.account_code and other_line.dc_marker == "D":
                        if line.amount.amount > 10000:
                            suspicious_combinations.append(
                                f"Large cash to expense: {line.amount.amount}"
                            )
        
        return {
            'suspicious': len(suspicious_combinations) > 0,
            'combinations': suspicious_combinations
        }
    
    async def _check_split_transactions(self, journal: JournalEntry) -> Dict[str, Any]:
        """Check for transaction structuring (splitting to avoid thresholds)"""
        
        # Look for multiple similar transactions just below threshold
        threshold = self.APPROVAL_THRESHOLD_LEVEL_1
        
        # Check for multiple transactions just below threshold
        near_threshold_count = 0
        for line in journal.lines:
            if threshold * 0.8 <= line.amount.amount < threshold:
                near_threshold_count += 1
        
        potential_structuring = near_threshold_count >= 3
        
        return {
            'potential_structuring': potential_structuring,
            'near_threshold_count': near_threshold_count,
            'threshold': threshold
        }
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    async def _get_period(self, period_date: date) -> Optional[PostingPeriod]:
        """Get posting period"""
        result = await self.db.execute(
            select(PostingPeriod).where(PostingPeriod.period_date == period_date)
        )
        return result.scalar_one_or_none()
    
    async def _check_unapproved_transactions(self, period_date: date) -> List[str]:
        """Check for unapproved high-value transactions"""
        # Implementation would query approval workflow table
        return []
    
    async def _check_trial_balance(self, period_date: date) -> Dict[str, Any]:
        """Check if trial balance is balanced"""
        # Query GL entries for period
        from ..models.database import GLEntries
        
        result = await self.db.execute(
            select(
                func.sum(GLEntries.amount).filter(GLEntries.acc_debit.isnot(None)).label('debits'),
                func.sum(GLEntries.amount).filter(GLEntries.acc_credit.isnot(None)).label('credits')
            ).where(GLEntries.trx_date == period_date)
        )
        
        row = result.one()
        debits = row.debits or Decimal(0)
        credits = row.credits or Decimal(0)
        
        return {
            'balanced': abs(debits - credits) < Decimal('0.01'),
            'debits': debits,
            'credits': credits,
            'difference': abs(debits - credits)
        }
    
    async def _check_reconciliation_status(self, period_date: date) -> Dict[str, Any]:
        """Check reconciliation status"""
        # Placeholder - would check reconciliation tables
        return {
            'complete': True,
            'pending_items': 0
        }
    
    async def _create_closing_entries(self, period_date: date) -> Dict[str, Any]:
        """Create period closing entries"""
        # Placeholder - would create accruals, deferrals, etc.
        return {'entries_created': 0}
    
    async def _calculate_period_pl(self, period_date: date) -> Dict[str, Any]:
        """Calculate period P&L"""
        # Placeholder - would calculate revenue and expenses
        return {'revenue': 0, 'expenses': 0, 'net_income': 0}
    
    async def _update_balance_sheet(self, period_date: date) -> Dict[str, Any]:
        """Update balance sheet"""
        # Placeholder - would update balance sheet accounts
        return {'assets': 0, 'liabilities': 0, 'equity': 0}
    
    async def _generate_compliance_reports(self, period_date: date) -> Dict[str, Any]:
        """Generate compliance reports"""
        # Placeholder - would generate various compliance reports
        return {'reports_generated': []}
    
    async def _auto_approve(self, journal: JournalEntry, context: AuditContext) -> Dict[str, Any]:
        """Auto-approve small amounts"""
        journal.status = JournalStatus.VALIDATED
        return {
            'status': 'AUTO_APPROVED',
            'approved_by': 'SYSTEM',
            'approved_at': datetime.utcnow()
        }
    
    async def _get_approvers(self, level: int, journal_type: str) -> List[int]:
        """Get list of approvers for level"""
        # Placeholder - would query user/role table
        if level == 1:
            return [2, 3]  # Supervisor IDs
        elif level == 2:
            return [4, 5]  # Manager IDs
        else:
            return [6]  # CFO ID
    
    async def _notify_approvers(self, workflow: ApprovalWorkflow, journal: JournalEntry):
        """Send notifications to approvers"""
        # Placeholder - would send emails/notifications
        pass
    
    async def _get_workflow(self, journal_id: UUID) -> Optional[ApprovalWorkflow]:
        """Get approval workflow for journal"""
        result = await self.db.execute(
            select(ApprovalWorkflow).where(
                and_(
                    ApprovalWorkflow.entity_type == "JOURNAL",
                    ApprovalWorkflow.entity_id == str(journal_id)
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _update_journal_status(self, journal_id: UUID, status: JournalStatus):
        """Update journal status"""
        await self.db.execute(
            update(SunJournal)
            .where(SunJournal.id == str(journal_id))
            .values(data=func.jsonb_set(SunJournal.data, '{status}', f'"{status}"'))
        )