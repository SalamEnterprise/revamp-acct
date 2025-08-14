"""
Voucher Service
Handles voucher creation and CSV export
"""

import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, update
from sqlalchemy.dialects.postgresql import insert

from ..models.domain import (
    Voucher, VoucherLine, JournalType, DCMarker,
    Money, TransactionCodes, CSVExportRequest, CSVExportResult
)
from ..models.database import SunJournal, SunVoucher
from ..core.cache import CacheService
from ..utils.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class VoucherService:
    """Service for voucher creation and export"""
    
    def __init__(
        self,
        db_session: AsyncSession,
        cache_service: CacheService,
        metrics_collector: MetricsCollector
    ):
        self.db = db_session
        self.cache = cache_service
        self.metrics = metrics_collector
    
    async def create_vouchers_for_date(self, journal_date: date) -> int:
        """
        Create vouchers for all unvouchered journals on a date
        
        Args:
            journal_date: Date to process
            
        Returns:
            Number of vouchers created
        """
        
        start_time = datetime.utcnow()
        voucher_count = 0
        
        try:
            # Get unvouchered journals grouped by type
            journal_groups = await self._get_unvouchered_journals(journal_date)
            
            for journal_type, journals in journal_groups.items():
                # Get next voucher sequence
                next_sequence = await self._get_next_voucher_sequence(
                    journal_date,
                    journal_type
                )
                
                # Group journals for consolidation
                voucher_groups = self._group_journals_for_vouchers(journals)
                
                for group_key, group_journals in voucher_groups.items():
                    # Create voucher
                    voucher = await self._create_voucher(
                        journal_date,
                        journal_type,
                        group_journals,
                        next_sequence
                    )
                    
                    # Save voucher
                    await self._save_voucher(voucher)
                    
                    # Update journals with voucher ID
                    await self._link_journals_to_voucher(
                        [j['id'] for j in group_journals],
                        voucher.id
                    )
                    
                    voucher_count += 1
                    next_sequence += 1
            
            await self.db.commit()
            
            # Update metrics
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.metrics.record_voucher_creation_time(execution_time)
            self.metrics.increment_vouchers_created(voucher_count)
            
        except Exception as e:
            logger.error(f"Error creating vouchers for {journal_date}: {e}")
            await self.db.rollback()
            raise
        
        return voucher_count
    
    async def _get_unvouchered_journals(
        self,
        journal_date: date
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get all unvouchered journals grouped by type"""
        
        query = select(SunJournal).where(
            and_(
                SunJournal.journal_date == journal_date,
                SunJournal.voucher_id.is_(None)
            )
        ).order_by(SunJournal.journal_type, SunJournal.id)
        
        result = await self.db.execute(query)
        journals = result.scalars().all()
        
        # Group by journal type
        grouped = {}
        for journal in journals:
            if journal.journal_type not in grouped:
                grouped[journal.journal_type] = []
            
            grouped[journal.journal_type].append({
                'id': journal.id,
                'data': journal.data,
                'source_rowid': journal.source_rowid
            })
        
        return grouped
    
    async def _get_next_voucher_sequence(
        self,
        journal_date: date,
        journal_type: str
    ) -> int:
        """Get next voucher sequence number"""
        
        # Query max voucher number for date and type
        query = select(func.max(func.substring(SunVoucher.voucher_no, 12, 4))).where(
            and_(
                SunVoucher.journal_date == journal_date,
                SunVoucher.journal_type == journal_type
            )
        )
        
        result = await self.db.execute(query)
        max_seq = result.scalar()
        
        if max_seq:
            return int(max_seq) + 1
        return 1
    
    def _group_journals_for_vouchers(
        self,
        journals: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group journals for voucher consolidation"""
        
        groups = {}
        
        for journal in journals:
            # Extract grouping key from journal data
            # Group by common characteristics
            journal_data = journal['data'].get('journal', [])
            
            if journal_data:
                first_line = journal_data[0].get('baris', [])
                if len(first_line) > 5:
                    # Create grouping key from journal source, number, and period
                    group_key = f"{first_line[1]}|{first_line[2]}|{first_line[5]}"
                else:
                    group_key = "default"
            else:
                group_key = "default"
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(journal)
        
        return groups
    
    async def _create_voucher(
        self,
        journal_date: date,
        journal_type: str,
        journals: List[Dict[str, Any]],
        sequence: int
    ) -> Voucher:
        """Create voucher from grouped journals"""
        
        # Generate voucher number: TypeYYMMDDSEQQ
        voucher_number = (
            f"{journal_type}"
            f"{journal_date.strftime('%y%m%d')}"
            f"{sequence:04d}"
        )
        
        # Aggregate journal lines
        voucher_lines = []
        journal_ids = []
        
        for journal in journals:
            journal_ids.append(UUID(journal['id']))
            
            # Process each journal line
            for line_data in journal['data'].get('journal', []):
                baris = line_data.get('baris', [])
                if len(baris) > 26:
                    # Create voucher line
                    voucher_line = VoucherLine(
                        line_number=int(baris[3]) if baris[3] else len(voucher_lines) + 1,
                        account_code=baris[7],
                        amount=Money(
                            amount=Decimal(baris[10]) if baris[10] else Decimal(0),
                            currency=baris[9] or "IDR"
                        ),
                        dc_marker=DCMarker(baris[13]) if baris[13] else DCMarker.DEBIT,
                        description=baris[8] or "",
                        transaction_codes=TransactionCodes(
                            t1=baris[17] if len(baris) > 17 else None,
                            t2=baris[18] if len(baris) > 18 else None,
                            t3=baris[19] if len(baris) > 19 else None,
                            t4=baris[20] if len(baris) > 20 else None,
                            t5=baris[21] if len(baris) > 21 else None,
                            t6=baris[22] if len(baris) > 22 else None,
                            t7=baris[23] if len(baris) > 23 else None,
                            t8=baris[24] if len(baris) > 24 else None,
                            t9=baris[25] if len(baris) > 25 else None,
                            t10=baris[26] if len(baris) > 26 else None
                        )
                    )
                    voucher_lines.append(voucher_line)
        
        # Consolidate lines by account
        consolidated_lines = self._consolidate_voucher_lines(voucher_lines)
        
        # Create voucher
        voucher = Voucher(
            voucher_number=voucher_number,
            journal_date=journal_date,
            journal_type=JournalType(journal_type),
            lines=consolidated_lines,
            journal_ids=journal_ids
        )
        
        return voucher
    
    def _consolidate_voucher_lines(
        self,
        lines: List[VoucherLine]
    ) -> List[VoucherLine]:
        """Consolidate voucher lines by account and DC marker"""
        
        consolidated = {}
        
        for line in lines:
            # Create consolidation key
            key = f"{line.account_code}|{line.dc_marker}|{line.transaction_codes.t1}|{line.transaction_codes.t2}"
            
            if key in consolidated:
                # Add amounts
                consolidated[key].amount = consolidated[key].amount.add(line.amount)
            else:
                consolidated[key] = VoucherLine(
                    line_number=len(consolidated) + 1,
                    account_code=line.account_code,
                    amount=line.amount,
                    dc_marker=line.dc_marker,
                    description=line.description,
                    transaction_codes=line.transaction_codes
                )
        
        # Renumber lines
        result = list(consolidated.values())
        for i, line in enumerate(result, 1):
            line.line_number = i
        
        return result
    
    async def _save_voucher(self, voucher: Voucher) -> None:
        """Save voucher to database"""
        
        # Format voucher data
        voucher_data = {
            'journal': [
                {
                    'baris': self._format_voucher_line(line, voucher)
                }
                for line in voucher.lines
            ]
        }
        
        # Create database record
        db_voucher = SunVoucher(
            id=str(voucher.id),
            journal_type=voucher.journal_type,
            journal_date=voucher.journal_date,
            voucher_no=voucher.voucher_number,
            data=voucher_data
        )
        
        self.db.add(db_voucher)
    
    def _format_voucher_line(
        self,
        line: VoucherLine,
        voucher: Voucher
    ) -> List[str]:
        """Format voucher line for storage (57 fields)"""
        
        fields = [
            voucher.journal_type,  # 0
            "SUN",  # 1 - Journal Source
            "",  # 2 - Journal Number
            str(line.line_number),  # 3
            voucher.voucher_number,  # 4 - Transaction Reference
            voucher.journal_date.strftime("%Y%m"),  # 5 - Accounting Period
            voucher.journal_date.isoformat(),  # 6 - Transaction Date
            line.account_code,  # 7
            line.description[:50],  # 8
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
        
        # Add empty fields (27-56)
        fields.extend([""] * 30)
        
        # Due date (57)
        fields.append("")
        
        return fields
    
    async def _link_journals_to_voucher(
        self,
        journal_ids: List[str],
        voucher_id: UUID
    ) -> None:
        """Update journals with voucher ID"""
        
        stmt = (
            update(SunJournal)
            .where(SunJournal.id.in_(journal_ids))
            .values(voucher_id=str(voucher_id))
        )
        
        await self.db.execute(stmt)
    
    async def export_vouchers_to_csv(
        self,
        request: CSVExportRequest
    ) -> CSVExportResult:
        """
        Export vouchers to CSV file
        
        Args:
            request: Export request parameters
            
        Returns:
            Export result with file path and metrics
        """
        
        # Query vouchers
        query = select(SunVoucher).where(
            and_(
                SunVoucher.journal_date >= request.start_date,
                SunVoucher.journal_date <= request.end_date
            )
        )
        
        if request.journal_types:
            query = query.where(
                SunVoucher.journal_type.in_(request.journal_types)
            )
        
        if not request.include_exported:
            query = query.where(SunVoucher.exported == False)
        
        query = query.order_by(SunVoucher.journal_date, SunVoucher.voucher_no)
        
        result = await self.db.execute(query)
        vouchers = result.scalars().all()
        
        if not vouchers:
            raise ValueError("No vouchers found for export")
        
        # Generate CSV
        csv_content = await self._generate_csv(vouchers)
        
        # Save to file
        file_path = await self._save_csv_file(csv_content, request.start_date, request.end_date)
        
        # Mark vouchers as exported
        voucher_ids = [UUID(v.id) for v in vouchers]
        await self._mark_vouchers_exported(voucher_ids)
        
        await self.db.commit()
        
        # Create result
        result = CSVExportResult(
            file_path=str(file_path),
            record_count=len(vouchers),
            file_size_bytes=len(csv_content.encode()),
            export_date=datetime.utcnow(),
            voucher_ids=voucher_ids
        )
        
        # Update metrics
        self.metrics.increment_csv_exports()
        
        return result
    
    async def _generate_csv(self, vouchers: List[SunVoucher]) -> str:
        """Generate CSV content from vouchers"""
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header (optional - depends on SUN system requirements)
        # writer.writerow(['Field1', 'Field2', ...])
        
        # Write voucher lines
        for voucher in vouchers:
            for line in voucher.data.get('journal', []):
                # Extract fields from line
                fields = line.get('baris', [])
                
                # Ensure 57 fields
                while len(fields) < 57:
                    fields.append("")
                
                # Write row
                writer.writerow(fields[:57])
        
        return output.getvalue()
    
    async def _save_csv_file(
        self,
        content: str,
        start_date: date,
        end_date: date
    ) -> Path:
        """Save CSV content to file"""
        
        # Create export directory
        export_dir = Path("exports")
        export_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"sun_export_{start_date}_{end_date}_{timestamp}.csv"
        file_path = export_dir / filename
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"CSV exported to {file_path}")
        
        return file_path
    
    async def _mark_vouchers_exported(self, voucher_ids: List[UUID]) -> None:
        """Mark vouchers as exported"""
        
        stmt = (
            update(SunVoucher)
            .where(SunVoucher.id.in_([str(vid) for vid in voucher_ids]))
            .values(
                exported=True,
                export_date=datetime.utcnow()
            )
        )
        
        await self.db.execute(stmt)