"""
Journal API Router
Endpoints for journal processing operations
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from ...models.domain import (
    ProcessingRequest, ProcessingResult, BatchProcessingResult,
    JournalEntry, JournalType, JournalStatus
)
from ...services.journal_service import JournalService
from ...core.cache import CacheService
from ...utils.metrics import MetricsCollector
from ..dependencies import get_db, get_cache, get_metrics_collector

logger = structlog.get_logger()

router = APIRouter()


@router.post("/process", response_model=ProcessingResult)
async def process_journal_date(
    request: ProcessingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache),
    metrics: MetricsCollector = Depends(get_metrics_collector)
):
    """
    Process journals for a specific date
    
    This endpoint triggers journal processing for the specified date.
    It will:
    1. Validate the request
    2. Check for existing journals (unless force_reprocess is True)
    3. Process journals from configured data sources
    4. Create GL entries
    5. Generate vouchers
    
    Returns processing metrics and status.
    """
    
    logger.info("Processing journal request", 
                journal_date=request.journal_date,
                force_reprocess=request.force_reprocess)
    
    try:
        # Create service
        journal_service = JournalService(db, cache, metrics)
        
        # Process journals
        result = await journal_service.process_journal_date(request)
        
        # Log result
        logger.info("Journal processing completed",
                   journal_date=request.journal_date,
                   status=result.status,
                   journals_created=result.journals_created,
                   vouchers_created=result.vouchers_created,
                   execution_time_ms=result.execution_time_ms)
        
        # Schedule background cleanup if successful
        if result.success:
            background_tasks.add_task(cleanup_old_data, db, request.journal_date)
        
        return result
        
    except Exception as e:
        logger.error("Error processing journals", 
                    error=str(e),
                    journal_date=request.journal_date)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-batch", response_model=BatchProcessingResult)
async def process_journal_batch(
    start_date: date,
    end_date: date,
    created_by: int,
    journal_types: Optional[List[JournalType]] = None,
    batch_size: int = Query(default=7, ge=1, le=31),
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache),
    metrics: MetricsCollector = Depends(get_metrics_collector)
):
    """
    Process journals for a date range
    
    Processes multiple dates in batch. Useful for:
    - Reprocessing historical data
    - Month-end processing
    - Catching up after downtime
    
    Parameters:
    - start_date: Start of date range
    - end_date: End of date range (inclusive)
    - created_by: User ID for audit
    - journal_types: Optional filter for specific journal types
    - batch_size: Number of days to process in parallel (default 7)
    """
    
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date must be before or equal to end date"
        )
    
    if (end_date - start_date).days > 365:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 365 days"
        )
    
    logger.info("Processing journal batch",
               start_date=start_date,
               end_date=end_date,
               batch_size=batch_size)
    
    try:
        journal_service = JournalService(db, cache, metrics)
        
        # Process batch
        results = []
        current_date = start_date
        total_journals = 0
        total_vouchers = 0
        total_time = 0
        successful_days = 0
        failed_days = 0
        
        while current_date <= end_date:
            # Process single date
            request = ProcessingRequest(
                journal_date=current_date,
                journal_types=journal_types,
                created_by=created_by,
                force_reprocess=False
            )
            
            result = await journal_service.process_journal_date(request)
            results.append(result)
            
            # Update totals
            total_journals += result.journals_created
            total_vouchers += result.vouchers_created
            total_time += result.execution_time_ms
            
            if result.success:
                successful_days += 1
            else:
                failed_days += 1
            
            # Move to next date
            current_date = current_date.replace(day=current_date.day + 1)
        
        # Create batch result
        batch_result = BatchProcessingResult(
            start_date=start_date,
            end_date=end_date,
            total_days=(end_date - start_date).days + 1,
            successful_days=successful_days,
            failed_days=failed_days,
            total_journals=total_journals,
            total_vouchers=total_vouchers,
            total_execution_time_ms=total_time,
            results=results
        )
        
        logger.info("Batch processing completed",
                   total_days=batch_result.total_days,
                   success_rate=batch_result.success_rate)
        
        return batch_result
        
    except Exception as e:
        logger.error("Error in batch processing", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{journal_date}")
async def get_journal_status(
    journal_date: date,
    journal_type: Optional[JournalType] = None,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache)
):
    """
    Get processing status for a specific date
    
    Returns:
    - Number of journals created
    - Number of vouchers created
    - Processing status
    - Last processing time
    """
    
    # Try cache first
    cache_key = f"status:{journal_date}:{journal_type}"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    
    # Query database
    from sqlalchemy import select, func
    from ...models.database import SunJournal, SunVoucher, ProcessingLog
    
    # Count journals
    journal_query = select(func.count()).select_from(SunJournal).where(
        SunJournal.journal_date == journal_date
    )
    if journal_type:
        journal_query = journal_query.where(SunJournal.journal_type == journal_type)
    
    journal_count = await db.scalar(journal_query)
    
    # Count vouchers
    voucher_query = select(func.count()).select_from(SunVoucher).where(
        SunVoucher.journal_date == journal_date
    )
    if journal_type:
        voucher_query = voucher_query.where(SunVoucher.journal_type == journal_type)
    
    voucher_count = await db.scalar(voucher_query)
    
    # Get last processing log
    log_query = select(ProcessingLog).where(
        ProcessingLog.process_date == journal_date
    ).order_by(ProcessingLog.created_date.desc()).limit(1)
    
    if journal_type:
        log_query = log_query.where(ProcessingLog.journal_type == journal_type)
    
    log_result = await db.execute(log_query)
    last_log = log_result.scalar_one_or_none()
    
    status = {
        "journal_date": journal_date,
        "journal_type": journal_type,
        "journal_count": journal_count or 0,
        "voucher_count": voucher_count or 0,
        "status": last_log.status if last_log else "NOT_PROCESSED",
        "last_processed": last_log.created_date if last_log else None,
        "execution_time_ms": float(last_log.execution_time_ms) if last_log else None
    }
    
    # Cache for 5 minutes
    await cache.set(cache_key, status, ttl=300)
    
    return status


@router.get("/", response_model=List[dict])
async def list_journals(
    start_date: date,
    end_date: Optional[date] = None,
    journal_type: Optional[JournalType] = None,
    status: Optional[JournalStatus] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    List journals with filtering
    
    Query parameters:
    - start_date: Start of date range
    - end_date: End of date range (optional)
    - journal_type: Filter by journal type
    - status: Filter by status
    - limit: Maximum records to return
    - offset: Number of records to skip
    """
    
    from sqlalchemy import select
    from ...models.database import SunJournal
    
    query = select(SunJournal).where(
        SunJournal.journal_date >= start_date
    )
    
    if end_date:
        query = query.where(SunJournal.journal_date <= end_date)
    
    if journal_type:
        query = query.where(SunJournal.journal_type == journal_type)
    
    if status:
        query = query.where(SunJournal.data['status'].astext == status)
    
    query = query.order_by(SunJournal.journal_date.desc(), SunJournal.id)
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    journals = result.scalars().all()
    
    return [
        {
            "id": j.id,
            "journal_date": j.journal_date,
            "journal_type": j.journal_type,
            "voucher_id": j.voucher_id,
            "status": j.data.get('status'),
            "created_date": j.created_date,
            "line_count": len(j.data.get('journal', [])),
            "total_amount": sum(
                float(line.get('baris', [0]*11)[10] or 0)
                for line in j.data.get('journal', [])
                if line.get('baris', [0]*14)[13] == 'D'
            )
        }
        for j in journals
    ]


@router.delete("/{journal_id}")
async def delete_journal(
    journal_id: str,
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache)
):
    """
    Delete a specific journal
    
    Warning: This operation cannot be undone and may affect vouchers.
    """
    
    from sqlalchemy import select, delete
    from ...models.database import SunJournal
    
    # Check if journal exists
    query = select(SunJournal).where(SunJournal.id == journal_id)
    result = await db.execute(query)
    journal = result.scalar_one_or_none()
    
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found")
    
    if journal.voucher_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete journal that has been vouchered"
        )
    
    # Delete journal
    stmt = delete(SunJournal).where(SunJournal.id == journal_id)
    await db.execute(stmt)
    await db.commit()
    
    # Clear cache
    await cache.delete(f"journal:{journal_id}")
    
    logger.info("Journal deleted", journal_id=journal_id)
    
    return {"message": "Journal deleted successfully", "journal_id": journal_id}


# Background tasks
async def cleanup_old_data(db: AsyncSession, current_date: date):
    """Background task to cleanup old data"""
    
    try:
        # Delete old test_table entries
        from sqlalchemy import delete
        from ...models.database import TestTable  # If exists
        
        cutoff_date = current_date.replace(year=current_date.year - 3)
        
        # Implement cleanup logic
        logger.info("Running cleanup task", cutoff_date=cutoff_date)
        
    except Exception as e:
        logger.error("Error in cleanup task", error=str(e))