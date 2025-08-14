"""
Domain Models for Insurance Journal System
Using Pydantic for validation and serialization
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict, field_validator, computed_field


# ==========================================
# Enums and Value Objects
# ==========================================

class JournalType(str, Enum):
    """Journal type enumeration"""
    S0980 = "S0980"
    S0990 = "S0990"
    S0470 = "S0470"
    S1470 = "S1470"
    # Add more types as needed

class JournalStatus(str, Enum):
    """Journal processing status"""
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    POSTED = "POSTED"
    VOUCHERED = "VOUCHERED"
    EXPORTED = "EXPORTED"
    ERROR = "ERROR"

class DCMarker(str, Enum):
    """Debit/Credit marker"""
    DEBIT = "D"
    CREDIT = "C"

class AccountFlag(int, Enum):
    """Account processing flag"""
    SKIP = 0
    IMMEDIATE = 1
    ACCUMULATE = 2
    POST_ACCUMULATED = 3
    POST_AND_ADJUST = 4


# ==========================================
# Value Objects
# ==========================================

class AccountCode(BaseModel):
    """Account code value object"""
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    
    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate account code format"""
        if not v.strip():
            raise ValueError("Account code cannot be empty")
        return v.strip().upper()

class Money(BaseModel):
    """Money value object with currency"""
    amount: Decimal = Field(..., ge=0, decimal_places=2)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    
    def add(self, other: 'Money') -> 'Money':
        """Add two money objects"""
        if self.currency != other.currency:
            raise ValueError(f"Cannot add different currencies: {self.currency} != {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)
    
    def subtract(self, other: 'Money') -> 'Money':
        """Subtract two money objects"""
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract different currencies: {self.currency} != {other.currency}")
        return Money(amount=self.amount - other.amount, currency=self.currency)

class TransactionCodes(BaseModel):
    """Transaction analysis codes (T1-T10)"""
    t1: Optional[str] = Field(None, description="Fund Type Code")
    t2: Optional[str] = Field(None, description="Policy Type")
    t3: Optional[str] = Field(None, description="Product Type")
    t4: Optional[str] = Field(None, description="Distribution Channel")
    t5: Optional[str] = Field(None, description="Location", default="3174")  # Jakarta Selatan
    t6: Optional[str] = Field(None, description="Economy Sector")
    t7: Optional[str] = Field(None, description="Unit")
    t8: Optional[str] = Field(None, description="Additional Code 8")
    t9: Optional[str] = Field(None, description="Additional Code 9")
    t10: Optional[str] = Field(None, description="Additional Code 10")
    
    @field_validator('t5')
    @classmethod
    def validate_location(cls, v: Optional[str]) -> str:
        """Default location if not provided"""
        return v or "3174"


# ==========================================
# Journal Domain Models
# ==========================================

class JournalLine(BaseModel):
    """Individual journal line entry"""
    line_number: int = Field(..., ge=1)
    account_code: str
    amount: Money
    dc_marker: DCMarker
    transaction_codes: TransactionCodes
    description: Optional[str] = Field(None, max_length=255)
    reference: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)

class JournalEntry(BaseModel):
    """Complete journal entry"""
    id: UUID = Field(default_factory=uuid4)
    journal_date: date
    journal_type: JournalType
    source_id: Optional[str] = None
    status: JournalStatus = JournalStatus.DRAFT
    lines: List[JournalLine]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_by: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    voucher_id: Optional[UUID] = None
    
    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('lines')
    @classmethod
    def validate_balanced(cls, v: List[JournalLine]) -> List[JournalLine]:
        """Validate that journal is balanced"""
        total_debits = Money(amount=Decimal(0), currency="IDR")
        total_credits = Money(amount=Decimal(0), currency="IDR")
        
        for line in v:
            if line.dc_marker == DCMarker.DEBIT:
                total_debits = total_debits.add(line.amount)
            else:
                total_credits = total_credits.add(line.amount)
        
        if total_debits.amount != total_credits.amount:
            raise ValueError(
                f"Journal is not balanced: Debits={total_debits.amount}, Credits={total_credits.amount}"
            )
        
        return v
    
    @computed_field
    @property
    def total_amount(self) -> Money:
        """Calculate total journal amount"""
        total = Decimal(0)
        for line in self.lines:
            if line.dc_marker == DCMarker.DEBIT:
                total += line.amount.amount
        return Money(amount=total, currency="IDR")
    
    @computed_field
    @property
    def line_count(self) -> int:
        """Get number of journal lines"""
        return len(self.lines)


# ==========================================
# Voucher Domain Models
# ==========================================

class VoucherLine(BaseModel):
    """Voucher line item"""
    line_number: int
    account_code: str
    amount: Money
    dc_marker: DCMarker
    description: str
    transaction_codes: TransactionCodes

class Voucher(BaseModel):
    """Voucher for CSV export"""
    id: UUID = Field(default_factory=uuid4)
    voucher_number: str
    journal_date: date
    journal_type: JournalType
    lines: List[VoucherLine]
    journal_ids: List[UUID]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    exported: bool = False
    export_date: Optional[datetime] = None
    
    model_config = ConfigDict(use_enum_values=True)
    
    @computed_field
    @property
    def total_amount(self) -> Money:
        """Calculate total voucher amount"""
        total = Decimal(0)
        for line in self.lines:
            if line.dc_marker == DCMarker.DEBIT:
                total += line.amount.amount
        return Money(amount=total, currency="IDR")


# ==========================================
# GL Entry Models
# ==========================================

class GLEntry(BaseModel):
    """General Ledger entry"""
    id: Optional[int] = None
    transaction_id: str
    account_debit: Optional[str] = None
    account_credit: Optional[str] = None
    amount: Money
    transaction_date: date
    transaction_codes: TransactionCodes
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('account_debit', 'account_credit')
    @classmethod
    def validate_accounts(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure at least one account is provided"""
        if info.field_name == 'account_credit' and not v and not info.data.get('account_debit'):
            raise ValueError("At least one account (debit or credit) must be provided")
        return v


# ==========================================
# Configuration Models
# ==========================================

class JournalSetting(BaseModel):
    """Journal type configuration"""
    journal_type: JournalType
    description: str
    status: int = 1
    status2: int = 0
    start_period: Optional[date] = None
    end_period: Optional[date] = None
    datasource_id: int
    row_configuration: List[Dict[str, Any]]
    
    def is_active_for_date(self, check_date: date) -> bool:
        """Check if setting is active for given date"""
        if self.status != 1:
            return False
            
        if not self.start_period and not self.end_period:
            return True
            
        if self.start_period and self.end_period:
            return self.start_period <= check_date <= self.end_period
            
        if self.end_period and self.status2 == 1:
            return check_date > self.end_period
            
        return False


# ==========================================
# Processing Models
# ==========================================

class ProcessingRequest(BaseModel):
    """Request to process journals for a date"""
    journal_date: date
    journal_types: Optional[List[JournalType]] = None
    created_by: int
    force_reprocess: bool = False

class ProcessingResult(BaseModel):
    """Result of journal processing"""
    journal_date: date
    status: str
    journals_created: int = 0
    vouchers_created: int = 0
    gl_entries_created: int = 0
    execution_time_ms: float = 0
    errors: List[str] = Field(default_factory=list)
    
    @computed_field
    @property
    def success(self) -> bool:
        """Check if processing was successful"""
        return self.status == "SUCCESS" and len(self.errors) == 0

class BatchProcessingResult(BaseModel):
    """Result of batch processing"""
    start_date: date
    end_date: date
    total_days: int
    successful_days: int
    failed_days: int
    total_journals: int
    total_vouchers: int
    total_execution_time_ms: float
    results: List[ProcessingResult]
    
    @computed_field
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_days == 0:
            return 0.0
        return (self.successful_days / self.total_days) * 100


# ==========================================
# Export Models
# ==========================================

class CSVExportRequest(BaseModel):
    """Request to export vouchers to CSV"""
    start_date: date
    end_date: date
    journal_types: Optional[List[JournalType]] = None
    include_exported: bool = False

class CSVExportResult(BaseModel):
    """Result of CSV export"""
    file_path: str
    record_count: int
    file_size_bytes: int
    export_date: datetime
    voucher_ids: List[UUID]


# ==========================================
# Monitoring Models
# ==========================================

class SystemMetrics(BaseModel):
    """System performance metrics"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    avg_processing_time_ms: float
    journals_per_second: float
    active_connections: int
    queue_size: int
    cache_hit_rate: float
    error_rate: float
    
class DataQualityMetrics(BaseModel):
    """Data quality metrics"""
    date: date
    total_records: int
    valid_records: int
    invalid_records: int
    missing_data_count: int
    duplicate_count: int
    
    @computed_field
    @property
    def quality_score(self) -> float:
        """Calculate data quality score"""
        if self.total_records == 0:
            return 0.0
        return (self.valid_records / self.total_records) * 100