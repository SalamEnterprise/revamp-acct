"""
Journal Processing Service
Core business logic for journal creation and processing
"""

import asyncio
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.dialects.postgresql import insert

from ..models.domain import (
    JournalEntry, JournalLine, JournalType, JournalStatus,
    DCMarker, Money, TransactionCodes, ProcessingRequest,
    ProcessingResult, JournalSetting, AccountCode
)
from ..models.database import (
    SunJournal, SunJournalSetting, GLEntries,
    ProcessingLog, DataQualityLog
)
from ..core.cache import CacheService
from ..core.exceptions import ValidationError, ProcessingError
from ..utils.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class JournalService:
    """Service for journal processing operations"""
    
    def __init__(
        self,
        db_session: AsyncSession,
        cache_service: CacheService,
        metrics_collector: MetricsCollector
    ):
        self.db = db_session
        self.cache = cache_service
        self.metrics = metrics_collector
        self.start_date_cutoff = date(2019, 5, 1)
    
    async def process_journal_date(
        self,
        request: ProcessingRequest
    ) -> ProcessingResult:
        """
        Process journals for a specific date
        
        Args:
            request: Processing request with date and parameters
            
        Returns:
            ProcessingResult with metrics and status
        """
        start_time = datetime.utcnow()
        result = ProcessingResult(
            journal_date=request.journal_date,
            status="PROCESSING"
        )
        
        try:
            # Validate date
            if request.journal_date < self.start_date_cutoff:
                result.status = "SKIPPED"
                result.errors.append(f"Date {request.journal_date} is before cutoff {self.start_date_cutoff}")
                return result
            
            # Check if already processed
            if not request.force_reprocess:
                existing = await self._check_existing_journals(request.journal_date)
                if existing > 0:
                    result.status = "ALREADY_PROCESSED"
                    result.errors.append(f"Date already has {existing} journals")
                    return result
            
            # Get active journal settings
            settings = await self._get_active_settings(request.journal_date, request.journal_types)
            if not settings:
                result.status = "NO_ACTIVE_SETTINGS"
                result.errors.append("No active journal settings found")
                return result
            
            # Process each journal type
            for setting in settings:
                try:
                    journals = await self._process_journal_type(
                        request.journal_date,
                        setting,
                        request.created_by
                    )
                    result.journals_created += len(journals)
                    
                    # Create GL entries
                    gl_count = await self._create_gl_entries(journals)
                    result.gl_entries_created += gl_count
                    
                except Exception as e:
                    logger.error(f"Error processing journal type {setting.journal_type}: {e}")
                    result.errors.append(f"Journal type {setting.journal_type}: {str(e)}")
            
            # Create vouchers
            if result.journals_created > 0:
                result.vouchers_created = await self._create_vouchers(request.journal_date)
            
            # Update status
            result.status = "SUCCESS" if len(result.errors) == 0 else "PARTIAL_SUCCESS"
            
        except Exception as e:
            logger.error(f"Fatal error processing date {request.journal_date}: {e}")
            result.status = "ERROR"
            result.errors.append(str(e))
        
        finally:
            # Calculate execution time
            result.execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Log processing result
            await self._log_processing_result(result, request.created_by)
            
            # Update metrics
            self.metrics.record_processing_time(result.execution_time_ms)
            self.metrics.increment_journals_created(result.journals_created)
            
        return result
    
    async def _check_existing_journals(self, journal_date: date) -> int:
        """Check if journals already exist for date"""
        query = select(func.count()).select_from(SunJournal).where(
            SunJournal.journal_date == journal_date
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def _get_active_settings(
        self,
        journal_date: date,
        journal_types: Optional[List[JournalType]] = None
    ) -> List[JournalSetting]:
        """Get active journal settings for date"""
        
        # Try cache first
        cache_key = f"settings:{journal_date}:{journal_types}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        
        # Query database
        query = select(SunJournalSetting).where(
            SunJournalSetting.status == 1
        )
        
        if journal_types:
            query = query.where(
                SunJournalSetting.journal_type.in_(journal_types)
            )
        
        result = await self.db.execute(query)
        db_settings = result.scalars().all()
        
        # Convert to domain models and filter by date
        settings = []
        for db_setting in db_settings:
            setting = JournalSetting(
                journal_type=db_setting.journal_type,
                description=db_setting.description,
                status=db_setting.status,
                status2=db_setting.status2,
                start_period=db_setting.journal_set.get('start_period'),
                end_period=db_setting.journal_set.get('end_period'),
                datasource_id=db_setting.journal_set.get('ds'),
                row_configuration=db_setting.journal_set.get('row', [])
            )
            
            if setting.is_active_for_date(journal_date):
                settings.append(setting)
        
        # Cache for 1 hour
        await self.cache.set(cache_key, settings, ttl=3600)
        
        return settings
    
    async def _process_journal_type(
        self,
        journal_date: date,
        setting: JournalSetting,
        created_by: int
    ) -> List[JournalEntry]:
        """Process journals for a specific type"""
        
        journals = []
        
        # Get data from source
        source_data = await self._get_source_data(
            journal_date,
            setting.datasource_id
        )
        
        for data_row in source_data:
            try:
                # Create journal entry
                journal = await self._create_journal_entry(
                    journal_date,
                    setting,
                    data_row,
                    created_by
                )
                
                # Validate journal
                await self._validate_journal(journal)
                
                # Save to database
                await self._save_journal(journal)
                
                journals.append(journal)
                
            except ValidationError as e:
                logger.warning(f"Validation error for journal: {e}")
                continue
            except Exception as e:
                logger.error(f"Error creating journal: {e}")
                raise
        
        return journals
    
    async def _get_source_data(
        self,
        journal_date: date,
        datasource_id: int
    ) -> List[Dict[str, Any]]:
        """Get source data from appropriate datasource function"""
        
        # Call appropriate function based on datasource_id
        # This would normally call the PostgreSQL functions
        # For now, returning mock data
        
        query = f"""
        SELECT * FROM fn_get_datasource_sun_journal(
            '{journal_date}'::date,
            {datasource_id},
            '{journal_date}'::date,
            '{journal_date}'::date
        )
        """
        
        result = await self.db.execute(query)
        return [dict(row) for row in result]
    
    async def _create_journal_entry(
        self,
        journal_date: date,
        setting: JournalSetting,
        source_data: Dict[str, Any],
        created_by: int
    ) -> JournalEntry:
        """Create journal entry from source data"""
        
        lines = []
        
        # Process each row configuration
        for row_config in setting.row_configuration:
            # Extract amount
            amount = self._extract_amount(source_data, row_config)
            if amount <= 0:
                continue
            
            # Create journal line
            line = JournalLine(
                line_number=row_config.get('journal_line_number', len(lines) + 1),
                account_code=self._get_account_code(source_data, row_config),
                amount=Money(amount=Decimal(str(amount)), currency="IDR"),
                dc_marker=DCMarker(row_config.get('d_c_marker', 'D')),
                transaction_codes=self._extract_transaction_codes(source_data, row_config),
                description=source_data.get('description', '')[:255],
                reference=source_data.get('transaction_reference')
            )
            
            lines.append(line)
        
        # Create journal entry
        journal = JournalEntry(
            journal_date=journal_date,
            journal_type=setting.journal_type,
            source_id=source_data.get('id'),
            status=JournalStatus.DRAFT,
            lines=lines,
            metadata={
                'spa_no': source_data.get('general_description_1'),
                'policy_no': source_data.get('general_description_2'),
                'participant_no': source_data.get('general_description_3'),
                'invoice_no': source_data.get('general_description_4'),
                'receipting_no': source_data.get('general_description_5'),
                'agent_code': source_data.get('general_description_6')
            },
            created_by=created_by
        )
        
        return journal
    
    def _extract_amount(
        self,
        source_data: Dict[str, Any],
        row_config: Dict[str, Any]
    ) -> float:
        """Extract transaction amount from source data"""
        
        # Check if amount is in row config
        if row_config.get('transaction_amount'):
            return float(row_config['transaction_amount'])
        
        # Extract from source data
        data_idx = row_config.get('data_idx', 0)
        amount_data = source_data.get('transaction_amount', {})
        
        if isinstance(amount_data, dict):
            amount = amount_data.get('amount', [])
            if isinstance(amount, list) and data_idx < len(amount):
                return float(amount[data_idx])
        
        return 0.0
    
    def _get_account_code(
        self,
        source_data: Dict[str, Any],
        row_config: Dict[str, Any]
    ) -> str:
        """Get account code with pattern matching"""
        
        account_code = row_config.get('account_code', '')
        
        # Pattern matching for dynamic account codes
        patterns = [
            'BANK', 'PREMI', 'PIUTANG', 'UTANG', 'KLAIM',
            'KONTRIBUSI', 'RUTIN', 'REMUN', 'FEE',
            'APPROPRIATE', 'BIAYA', 'KOMISI'
        ]
        
        if any(pattern in account_code.upper() for pattern in patterns):
            # Use lookup from source data
            data_idx = row_config.get('data_idx', 0)
            account_data = source_data.get('account_code', {})
            
            if isinstance(account_data, dict):
                accounts = account_data.get('account', [])
                if isinstance(accounts, list) and data_idx < len(accounts):
                    return accounts[data_idx]
        
        return account_code
    
    def _extract_transaction_codes(
        self,
        source_data: Dict[str, Any],
        row_config: Dict[str, Any]
    ) -> TransactionCodes:
        """Extract transaction codes (T1-T10)"""
        
        codes = {}
        
        for i in range(1, 11):
            t_key = f't{i}'
            t_code = row_config.get(f'{t_key}_code')
            
            if not t_code:
                # Get from source data
                t_data = source_data.get(t_key, {})
                if isinstance(t_data, dict):
                    t_code = t_data.get(t_key, [''])[0] if t_key in t_data else ''
            
            codes[t_key] = t_code if t_code and t_code != '' else None
        
        return TransactionCodes(**codes)
    
    async def _validate_journal(self, journal: JournalEntry) -> None:
        """Validate journal entry"""
        
        # Check if balanced (already done in model validation)
        # Additional business rules validation here
        
        if len(journal.lines) == 0:
            raise ValidationError("Journal has no lines")
        
        if journal.total_amount.amount == 0:
            raise ValidationError("Journal total amount is zero")
        
        journal.status = JournalStatus.VALIDATED
    
    async def _save_journal(self, journal: JournalEntry) -> None:
        """Save journal to database"""
        
        # Convert to database model
        db_journal = SunJournal(
            id=str(journal.id),
            source_rowid=journal.source_id,
            data={
                'journal': [
                    {
                        'baris': self._format_journal_line(line, journal)
                    }
                    for line in journal.lines
                ],
                'journal_date': journal.journal_date.isoformat(),
                'journal_type': journal.journal_type
            },
            journal_type=journal.journal_type,
            journal_date=journal.journal_date,
            created_by=journal.created_by,
            search_id=[journal.metadata.get('participant_no')]
        )
        
        # Insert or update
        stmt = insert(SunJournal).values(
            id=db_journal.id,
            source_rowid=db_journal.source_rowid,
            data=db_journal.data,
            journal_type=db_journal.journal_type,
            journal_date=db_journal.journal_date,
            created_by=db_journal.created_by,
            search_id=db_journal.search_id
        ).on_conflict_do_nothing(
            index_elements=['source_rowid', 'journal_type']
        )
        
        await self.db.execute(stmt)
        await self.db.commit()
        
        journal.status = JournalStatus.POSTED
    
    def _format_journal_line(
        self,
        line: JournalLine,
        journal: JournalEntry
    ) -> List[str]:
        """Format journal line for storage (57 fields)"""
        
        fields = [
            journal.journal_type,  # 0
            "SUN",  # 1 - Journal Source
            "",  # 2 - Journal Number
            str(line.line_number),  # 3
            line.reference or "",  # 4 - Transaction Reference
            journal.journal_date.strftime("%Y%m"),  # 5 - Accounting Period
            journal.journal_date.isoformat(),  # 6 - Transaction Date
            line.account_code,  # 7
            line.description or "",  # 8
            line.amount.currency,  # 9
            str(line.amount.amount),  # 10
            "1",  # 11 - Currency Rate
            str(line.amount.amount),  # 12 - Base Amount
            line.dc_marker,  # 13
            "",  # 14 - Asset Indicator
            "",  # 15 - Asset Code
            "",  # 16 - Asset Sub Code
            line.transaction_codes.t1 or "",  # 17
            line.transaction_codes.t2 or "",  # 18
            line.transaction_codes.t3 or "",  # 19
            line.transaction_codes.t4 or "",  # 20
            line.transaction_codes.t5 or "",  # 21
            line.transaction_codes.t6 or "",  # 22
            line.transaction_codes.t7 or "",  # 23
            line.transaction_codes.t8 or "",  # 24
            line.transaction_codes.t9 or "",  # 25
            line.transaction_codes.t10 or "",  # 26
        ]
        
        # Add general descriptions (27-32)
        for i in range(1, 7):
            fields.append(journal.metadata.get(f'general_description_{i}', ''))
        
        # Add empty fields (33-56)
        fields.extend([""] * 24)
        
        # Due date (57)
        fields.append("")
        
        return fields
    
    async def _create_gl_entries(self, journals: List[JournalEntry]) -> int:
        """Create GL entries from journals"""
        
        gl_count = 0
        
        for journal in journals:
            for line in journal.lines:
                # Determine account flag logic
                # For now, create GL entry for all lines
                
                gl_entry = GLEntries(
                    trx_id=journal.metadata.get('transaction_reference', str(journal.id)),
                    acc_debit=line.account_code if line.dc_marker == DCMarker.DEBIT else None,
                    acc_credit=line.account_code if line.dc_marker == DCMarker.CREDIT else None,
                    amount=line.amount.amount,
                    trx_date=journal.journal_date,
                    t_1=line.transaction_codes.t1,
                    t_2=line.transaction_codes.t2,
                    t_3=line.transaction_codes.t3,
                    t_4=line.transaction_codes.t4,
                    t_5=line.transaction_codes.t5,
                    t_6=line.transaction_codes.t6,
                    t_7=line.transaction_codes.t7,
                    t_8=line.transaction_codes.t8,
                    t_9=line.transaction_codes.t9,
                    t_10=line.transaction_codes.t10,
                    data={
                        'journal_id': str(journal.id),
                        'journal_type': journal.journal_type,
                        'line_number': line.line_number
                    }
                )
                
                self.db.add(gl_entry)
                gl_count += 1
        
        await self.db.commit()
        return gl_count
    
    async def _create_vouchers(self, journal_date: date) -> int:
        """Create vouchers from journals"""
        
        # This would call the voucher service
        # For now, return mock count
        from .voucher_service import VoucherService
        
        voucher_service = VoucherService(self.db, self.cache, self.metrics)
        return await voucher_service.create_vouchers_for_date(journal_date)
    
    async def _log_processing_result(
        self,
        result: ProcessingResult,
        created_by: int
    ) -> None:
        """Log processing result to database"""
        
        log_entry = ProcessingLog(
            process_date=result.journal_date,
            status=result.status,
            journals_created=result.journals_created,
            vouchers_created=result.vouchers_created,
            gl_entries_created=result.gl_entries_created,
            execution_time_ms=result.execution_time_ms,
            error_message='; '.join(result.errors) if result.errors else None,
            created_by=created_by
        )
        
        self.db.add(log_entry)
        await self.db.commit()