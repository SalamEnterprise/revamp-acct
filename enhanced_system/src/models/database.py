"""
SQLAlchemy Database Models for Enhanced Journal System
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Integer, Date, DateTime, Numeric, 
    Boolean, ForeignKey, Text, JSON, ARRAY, Index,
    UniqueConstraint, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import text

Base = declarative_base()


# ==========================================
# Journal Tables
# ==========================================

class SunJournal(Base):
    """Journal entries table"""
    __tablename__ = 'sun_journal'
    
    id = Column(String(32), primary_key=True, default=lambda: str(func.uuid_generate_v4()))
    source_rowid = Column(String(32), index=True)
    voucher_id = Column(String(32), ForeignKey('sun_voucher.id'), index=True)
    data = Column(JSONB, nullable=False)
    journal_type = Column(String(5), nullable=False, index=True)
    journal_date = Column(Date, nullable=False, index=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer)
    search_id = Column(ARRAY(String))
    
    # Relationships
    voucher = relationship("SunVoucher", back_populates="journals")
    
    # Indexes
    __table_args__ = (
        Index('idx_sun_journal_date_type', 'journal_date', 'journal_type'),
        Index('idx_sun_journal_unvouchered', 'journal_date', 'journal_type', 
              postgresql_where=text('voucher_id IS NULL')),
        Index('idx_sun_journal_data_gin', 'data', postgresql_using='gin'),
        Index('idx_sun_journal_search_id', 'search_id', postgresql_using='gin'),
        UniqueConstraint('source_rowid', 'journal_type', name='uq_sun_journal_source'),
    )
    
    @validates('journal_type')
    def validate_journal_type(self, key, value):
        """Validate journal type format"""
        if not value or len(value) > 5:
            raise ValueError(f"Invalid journal type: {value}")
        return value.upper()


class SunVoucher(Base):
    """Voucher table for CSV export"""
    __tablename__ = 'sun_voucher'
    
    id = Column(String(32), primary_key=True, default=lambda: str(func.uuid_generate_v4()))
    journal_type = Column(String(5), nullable=False, index=True)
    journal_date = Column(Date, nullable=False, index=True)
    voucher_no = Column(String(20), unique=True, nullable=False, index=True)
    data = Column(JSONB, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    exported = Column(Boolean, default=False)
    export_date = Column(DateTime)
    
    # Relationships
    journals = relationship("SunJournal", back_populates="voucher")
    
    # Indexes
    __table_args__ = (
        Index('idx_sun_voucher_date_type', 'journal_date', 'journal_type'),
        Index('idx_sun_voucher_unexported', 'journal_date', 
              postgresql_where=text('exported = false')),
    )


class SunJournalSetting(Base):
    """Journal configuration settings"""
    __tablename__ = 'sun_journal_setting'
    
    journal_type = Column(String(5), primary_key=True)
    description = Column(String(255))
    status = Column(Integer, default=1)
    status2 = Column(Integer, default=0)
    journal_set = Column(JSONB)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_sun_journal_setting_active', 'journal_type',
              postgresql_where=text('status = 1')),
        Index('idx_sun_journal_setting_jsonb', 'journal_set', postgresql_using='gin'),
    )


# ==========================================
# GL Tables
# ==========================================

class GLEntries(Base):
    """General Ledger entries"""
    __tablename__ = 'gl_entries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trx_id = Column(String(100), index=True)
    acc_debit = Column(String(50))
    acc_credit = Column(String(50))
    amount = Column(Numeric(20, 2), nullable=False)
    trx_date = Column(Date, nullable=False, index=True)
    t_1 = Column(String(20))
    t_2 = Column(String(20))
    t_3 = Column(String(20))
    t_4 = Column(String(20))
    t_5 = Column(String(20))
    t_6 = Column(String(20))
    t_7 = Column(String(20))
    t_8 = Column(String(20))
    t_9 = Column(String(20))
    t_10 = Column(String(20))
    data = Column(JSON)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_gl_entries_date', 'trx_date'),
        Index('idx_gl_entries_accounts', 'acc_debit', 'acc_credit'),
        Index('idx_gl_entries_t_codes', 't_1', 't_2', 't_3', 't_4', 't_5'),
        Index('idx_gl_entries_date_accounts', 'trx_date', 'acc_debit', 'acc_credit'),
        CheckConstraint('acc_debit IS NOT NULL OR acc_credit IS NOT NULL', 
                       name='check_gl_entries_account'),
    )
    
    @validates('amount')
    def validate_amount(self, key, value):
        """Validate amount is positive"""
        if value and value < 0:
            raise ValueError(f"Amount must be positive: {value}")
        return value


# ==========================================
# Lookup Tables
# ==========================================

class SunTcodeLookup(Base):
    """Transaction code lookup table"""
    __tablename__ = 'sun_tcode_lookup'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_dimension = Column(String(10), nullable=False)
    analysis_code = Column(String(20), nullable=False)
    description = Column(String(255))
    active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('analysis_dimension', 'analysis_code', 
                        name='uq_sun_tcode_lookup'),
        Index('idx_sun_tcode_lookup_active', 'analysis_dimension', 'analysis_code',
              postgresql_where=text('active = true')),
    )


# ==========================================
# Audit and Monitoring Tables
# ==========================================

class ProcessingLog(Base):
    """Journal processing audit log"""
    __tablename__ = 'processing_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    process_date = Column(Date, nullable=False)
    journal_type = Column(String(5))
    status = Column(String(20), nullable=False)
    journals_created = Column(Integer, default=0)
    vouchers_created = Column(Integer, default=0)
    gl_entries_created = Column(Integer, default=0)
    execution_time_ms = Column(Numeric(10, 2))
    error_message = Column(Text)
    created_by = Column(Integer)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_processing_log_date', 'process_date'),
        Index('idx_processing_log_status', 'status'),
        Index('idx_processing_log_date_type', 'process_date', 'journal_type'),
    )


class DataQualityLog(Base):
    """Data quality metrics log"""
    __tablename__ = 'data_quality_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    check_date = Column(Date, nullable=False)
    table_name = Column(String(50), nullable=False)
    total_records = Column(Integer, default=0)
    valid_records = Column(Integer, default=0)
    invalid_records = Column(Integer, default=0)
    missing_data_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    quality_score = Column(Numeric(5, 2))
    check_details = Column(JSONB)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_data_quality_log_date', 'check_date'),
        Index('idx_data_quality_log_table', 'table_name'),
        Index('idx_data_quality_log_score', 'quality_score'),
    )


class PerformanceMetrics(Base):
    """System performance metrics"""
    __tablename__ = 'performance_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    metric_type = Column(String(50), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Numeric(20, 4))
    metric_unit = Column(String(20))
    metadata = Column(JSONB)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_performance_metrics_date', 'metric_date'),
        Index('idx_performance_metrics_type', 'metric_type'),
        Index('idx_performance_metrics_name', 'metric_name'),
    )


# ==========================================
# Archive Tables (for historical data)
# ==========================================

class SunJournalArchive(Base):
    """Archive table for old journal entries"""
    __tablename__ = 'sun_journal_archive'
    
    id = Column(String(32), primary_key=True)
    source_rowid = Column(String(32))
    voucher_id = Column(String(32))
    data = Column(JSONB)
    journal_type = Column(String(5))
    journal_date = Column(Date)
    created_date = Column(DateTime)
    created_by = Column(Integer)
    search_id = Column(ARRAY(String))
    archived_date = Column(DateTime, default=datetime.utcnow)
    
    # Indexes for archive table (fewer indexes for storage optimization)
    __table_args__ = (
        Index('idx_sun_journal_archive_date', 'journal_date'),
        Index('idx_sun_journal_archive_type', 'journal_type'),
    )


# ==========================================
# Cache Tables
# ==========================================

class ConfigCache(Base):
    """Configuration cache table"""
    __tablename__ = 'config_cache'
    
    cache_key = Column(String(100), primary_key=True)
    cache_value = Column(JSONB, nullable=False)
    expires_at = Column(DateTime)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_config_cache_expires', 'expires_at'),
    )
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at


# ==========================================
# Materialized View Models (for ORM access)
# ==========================================

class MVJournalDailySummary(Base):
    """Materialized view for journal daily summary"""
    __tablename__ = 'mv_journal_daily_summary'
    
    journal_date = Column(Date, primary_key=True)
    journal_type = Column(String(5), primary_key=True)
    entry_count = Column(Integer)
    unique_sources = Column(Integer)
    unvouchered_count = Column(Integer)
    vouchered_count = Column(Integer)
    total_amount = Column(Numeric(20, 2))
    avg_amount = Column(Numeric(20, 2))
    first_created = Column(DateTime)
    last_created = Column(DateTime)
    statuses = Column(ARRAY(String))
    
    # Mark as view (read-only)
    __table_args__ = {'info': {'is_view': True}}


class MVAccountBalance(Base):
    """Materialized view for account balances"""
    __tablename__ = 'mv_account_balance'
    
    trx_date = Column(Date, primary_key=True)
    acc_debit = Column(String(50), primary_key=True)
    acc_credit = Column(String(50), primary_key=True)
    transaction_count = Column(Integer)
    total_amount = Column(Numeric(20, 2))
    avg_amount = Column(Numeric(20, 2))
    min_amount = Column(Numeric(20, 2))
    max_amount = Column(Numeric(20, 2))
    t1_codes = Column(String)
    t2_codes = Column(String)
    t3_codes = Column(String)
    
    # Mark as view (read-only)
    __table_args__ = {'info': {'is_view': True}}