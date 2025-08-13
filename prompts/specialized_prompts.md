# Specialized Domain-Specific Prompt Templates

## Insurance Domain Specialist Prompts

### 1. Insurance Product Mapping Analysis

```
Analyze the journal system for insurance-specific product handling:

## Product Type Analysis
1. **Product Classification**
   - Identify all insurance product types (Life, Health, Property, etc.)
   - Map product codes to T-codes (T1-T10)
   - Document product-specific journal rules
   - Identify unit-linked vs traditional products

2. **Premium Processing Logic**
   - Regular premium collection flows
   - Single premium handling
   - Top-up premium processing
   - Premium allocation rules (mortality, investment, admin fees)

3. **Claim Type Handling**
   - Death claims
   - Maturity claims
   - Surrender values
   - Partial withdrawals
   - Disability/Critical illness claims

## Regulatory Compliance Mapping
- OJK (Indonesian FSA) requirements
- PSAK 108 (Sharia insurance accounting)
- IFRS 17 compliance readiness
- Solvency calculation impacts

## Deliverables
- Product-journal mapping matrix
- Regulatory compliance checklist
- Product-specific validation rules
- Recommended enhancements for new products
```

### 2. Reinsurance Treaty Processing

```
Analyze reinsurance transaction handling in the journal system:

## Treaty Analysis
1. **Treaty Types**
   - Quota share identification
   - Surplus arrangements
   - Excess of loss treaties
   - Facultative reinsurance

2. **Journal Entry Patterns**
   - Ceded premium calculations
   - Commission receivables
   - Claim recoveries
   - Reserve adjustments

3. **Reconciliation Requirements**
   - Bordereaux preparation
   - Account current matching
   - Outstanding claims tracking
   - IBNR allocations

## Enhancement Opportunities
- Automated treaty allocation
- Real-time reinsurance calculations
- Automated bordereaux generation
- Treaty limit monitoring
```

### 3. Investment-Linked (Unit Link) Specialization

```
Deep dive into unit-linked insurance transaction processing:

## Unit Price Processing
1. **NAV Calculations**
   - Daily unit price updates
   - Forward pricing implementation
   - Bid-offer spread handling
   - Fund switching logic

2. **Unit Allocation**
   - Premium to unit conversion
   - Mortality deduction timing
   - Fund management fee calculations
   - Loyalty bonus allocations

3. **Transaction Types**
   - Unit purchases
   - Unit redemptions
   - Switches between funds
   - Regular withdrawals

## Reconciliation Points
- Unit registry vs GL reconciliation
- Investment portfolio matching
- Fee calculation verification
- Performance attribution

## Modernization Recommendations
- Real-time unit pricing integration
- Automated fund rebalancing
- Performance reporting enhancement
- Multi-currency support
```

## Banking Integration Specialist Prompts

### 4. Bank Reconciliation Optimization

```
Analyze bank reconciliation processes in detail:

## Current State Assessment
1. **Reconciliation Points**
   - Bank statement parsing logic
   - Transaction matching algorithms
   - Exception handling processes
   - Unmatched item aging

2. **Integration Patterns**
   - Bank API integrations
   - File format handling (MT940, BAI2, etc.)
   - Real-time vs batch processing
   - Multi-bank consolidation

3. **Common Issues**
   - Timing differences
   - Commission/fee reconciliation
   - Foreign exchange handling
   - Reversed transaction handling

## Automation Opportunities
- ML-based transaction matching
- Automated exception resolution
- Real-time reconciliation
- Predictive cash management

## Deliverables
- Reconciliation process flow
- Exception handling matrix
- Automation roadmap
- Bank integration architecture
```

### 5. Payment Gateway Integration

```
Design modern payment processing integration:

## Payment Channel Analysis
1. **Current Channels**
   - Virtual accounts
   - Credit/debit cards
   - E-wallets
   - Bank transfers
   - Mobile banking

2. **Transaction Flows**
   - Payment initiation
   - Confirmation handling
   - Failed payment recovery
   - Refund processing

3. **Settlement Processing**
   - T+n settlement patterns
   - Merchant fee calculations
   - Tax handling
   - Multi-currency conversion

## Modernization Approach
- API-first payment integration
- Webhook-based notifications
- Idempotency implementation
- Circuit breaker patterns

## Compliance Requirements
- PCI-DSS compliance
- ISO 20022 messaging
- Open banking standards
- AML/CFT requirements
```

## Technical Specialist Prompts

### 6. JSONB Optimization Specialist

```
Perform deep analysis of JSONB usage and optimization:

## JSONB Structure Analysis
1. **Current Usage Patterns**
   - Document all JSONB columns
   - Analyze JSON structure depth
   - Identify repeated patterns
   - Calculate storage overhead

2. **Query Performance**
   - Identify slow JSONB queries
   - Analyze GIN index usage
   - Find missing path indexes
   - Optimize containment queries

3. **Refactoring Opportunities**
   - Candidates for normalization
   - Schema extraction possibilities
   - Compression opportunities
   - Partitioning strategies

## Optimization Techniques
```sql
-- Example optimizations to implement
-- Partial indexes for common queries
CREATE INDEX idx_journal_pending 
ON sun_journal((data->>'status')) 
WHERE data->>'status' = 'PENDING';

-- Path-based GIN indexes
CREATE INDEX idx_journal_paths 
ON sun_journal USING GIN ((data->'journal'->'entries'));

-- Expression indexes for computed values
CREATE INDEX idx_journal_amount 
ON sun_journal(((data->>'amount')::numeric));
```

## Migration Strategy
- Gradual schema extraction
- Backward compatibility approach
- Performance testing framework
- Rollback procedures
```

### 7. Temporal Data Specialist

```
Design temporal data handling and audit strategy:

## Temporal Requirements Analysis
1. **Time Dimensions**
   - Transaction time vs valid time
   - Effective dating requirements
   - Retroactive adjustments
   - Future-dated transactions

2. **Audit Trail Design**
   - Change data capture (CDC)
   - Temporal tables implementation
   - Point-in-time recovery
   - Audit query optimization

3. **Historical Data Management**
   - Archival strategies
   - Compression techniques
   - Partition maintenance
   - Historical reporting

## Implementation Approach
```sql
-- Temporal table design
CREATE TABLE journal_temporal (
    id UUID,
    data JSONB,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP,
    transaction_time TIMESTAMP DEFAULT NOW(),
    modified_by VARCHAR(100),
    modification_reason TEXT,
    PERIOD FOR valid_time (valid_from, valid_to)
);

-- System versioning
ALTER TABLE journal_temporal 
ADD SYSTEM VERSIONING 
HISTORY_TABLE = journal_history;
```

## Query Patterns
- Point-in-time queries
- Period overlap queries
- Change history queries
- Temporal joins
```

### 8. Batch to Stream Migration Specialist

```
Transform batch processing to real-time stream processing:

## Stream Processing Assessment
1. **Current Batch Windows**
   - Identify batch job schedules
   - Calculate processing delays
   - Find dependencies between batches
   - Measure batch failure impacts

2. **Streaming Candidates**
   - Real-time suitable transactions
   - Near-real-time requirements
   - Micro-batch opportunities
   - Pure streaming candidates

3. **Technology Selection**
   - Apache Kafka vs Pulsar vs Kinesis
   - Stream processing (Flink vs Spark Streaming)
   - State management requirements
   - Exactly-once semantics

## Implementation Design
```python
# Kafka Streams example
class JournalStreamProcessor:
    def __init__(self):
        self.builder = StreamsBuilder()
        
    def build_topology(self):
        # Input stream
        transactions = self.builder.stream('transactions')
        
        # Enrichment
        enriched = transactions.join(
            account_table,
            lambda tx, acc: self.enrich_transaction(tx, acc)
        )
        
        # Validation
        validated = enriched.filter(
            lambda tx: self.validate_business_rules(tx)
        )
        
        # Journal creation
        journals = validated.map(
            lambda tx: self.create_journal_entry(tx)
        )
        
        # Output streams
        journals.to('journals')
        journals.filter(lambda j: j.requires_approval).to('approval-queue')
        
        return self.builder.build()
```

## Migration Strategy
- Parallel run approach
- Gradual cutover plan
- Backpressure handling
- State migration approach
```

## Data Quality Specialist Prompts

### 9. Data Quality Framework Design

```
Design comprehensive data quality management framework:

## Data Quality Dimensions
1. **Completeness**
   - Mandatory field validation
   - Referential integrity checks
   - Coverage metrics
   - Missing data patterns

2. **Accuracy**
   - Business rule validation
   - Cross-field validation
   - External reference validation
   - Calculation verification

3. **Consistency**
   - Cross-system validation
   - Temporal consistency
   - Duplicate detection
   - Format standardization

4. **Timeliness**
   - Processing delay metrics
   - Data freshness indicators
   - SLA monitoring
   - Aging analysis

## Implementation Framework
```python
class DataQualityFramework:
    def __init__(self):
        self.rules = []
        self.metrics = {}
        
    def add_rule(self, rule: DataQualityRule):
        self.rules.append(rule)
        
    def validate_batch(self, data: DataFrame) -> ValidationReport:
        results = []
        for rule in self.rules:
            result = rule.validate(data)
            results.append(result)
            self.update_metrics(result)
        return ValidationReport(results)
    
    def generate_quality_score(self) -> float:
        # Weighted quality score calculation
        weights = {
            'completeness': 0.3,
            'accuracy': 0.4,
            'consistency': 0.2,
            'timeliness': 0.1
        }
        return sum(
            self.metrics[dim] * weight 
            for dim, weight in weights.items()
        )
```

## Monitoring and Alerting
- Real-time quality dashboards
- Automated anomaly detection
- Quality trend analysis
- Root cause analysis tools
```

### 10. Regulatory Reporting Specialist

```
Design regulatory reporting extraction and automation:

## Regulatory Requirements Mapping
1. **Report Inventory**
   - List all regulatory reports
   - Map data sources per report
   - Identify calculation logic
   - Document submission schedules

2. **Data Lineage**
   - Source to report mapping
   - Transformation documentation
   - Validation points
   - Approval workflows

3. **Automation Opportunities**
   - Report generation automation
   - Validation automation
   - Submission automation
   - Exception handling

## XBRL/Regulatory Format Generation
```python
class RegulatoryReportGenerator:
    def __init__(self, report_config: ReportConfig):
        self.config = report_config
        self.validators = []
        
    def generate_ojk_report(self, period: Period) -> XBRLDocument:
        # Extract data
        data = self.extract_period_data(period)
        
        # Apply regulatory calculations
        calculated = self.apply_regulatory_rules(data)
        
        # Validate against taxonomy
        self.validate_taxonomy(calculated)
        
        # Generate XBRL
        xbrl = XBRLDocument()
        for fact in calculated:
            xbrl.add_fact(
                concept=fact.concept,
                value=fact.value,
                context=fact.context,
                unit=fact.unit
            )
        
        return xbrl
    
    def validate_submission(self, xbrl: XBRLDocument) -> ValidationResult:
        # Schema validation
        # Business rule validation
        # Cross-period validation
        pass
```

## Compliance Calendar Integration
- Automated deadline tracking
- Submission status monitoring
- Regulatory change management
- Audit trail maintenance
```

## Advanced Integration Prompts

### 11. API Gateway and Integration Layer Design

```
Design comprehensive API strategy for the journal system:

## API Architecture
1. **API Inventory**
   - Internal APIs needed
   - External API integrations
   - Partner API requirements
   - Public API considerations

2. **API Design Principles**
   - RESTful vs GraphQL vs gRPC
   - Versioning strategy
   - Rate limiting approach
   - Authentication/Authorization

3. **Integration Patterns**
   - Synchronous vs asynchronous
   - Request-reply vs event-driven
   - Compensation patterns
   - Circuit breaker implementation

## API Gateway Configuration
```yaml
# Kong/AWS API Gateway configuration example
services:
  - name: journal-service
    url: http://journal-service:8080
    routes:
      - name: create-journal
        paths: ["/api/v1/journals"]
        methods: ["POST"]
        plugins:
          - name: rate-limiting
            config:
              minute: 100
              policy: local
          - name: jwt
            config:
              secret_is_base64: false
          - name: request-transformer
            config:
              add:
                headers:
                  - X-Trace-Id:$(uuid)
          - name: response-transformer
            config:
              add:
                headers:
                  - X-Rate-Limit-Remaining:$(rate_limit_remaining)
```

## Integration Security
- OAuth 2.0/OIDC implementation
- API key management
- Certificate pinning
- Request signing
```

### 12. Disaster Recovery and Business Continuity

```
Design comprehensive DR/BC strategy:

## Recovery Requirements Analysis
1. **RPO/RTO Analysis**
   - Define RPO per system component
   - Define RTO per system component
   - Identify critical path
   - Document dependencies

2. **Failure Scenarios**
   - Data center failure
   - Database corruption
   - Ransomware attack
   - Natural disasters

3. **Recovery Strategies**
   - Hot standby vs warm standby
   - Active-active vs active-passive
   - Backup strategies
   - Replication approach

## Implementation Plan
```bash
# PostgreSQL streaming replication setup
# Primary configuration
postgresql.conf:
  wal_level = replica
  max_wal_senders = 3
  wal_keep_segments = 64
  synchronous_commit = on
  synchronous_standby_names = 'standby1'

# Standby configuration
recovery.conf:
  standby_mode = 'on'
  primary_conninfo = 'host=primary port=5432 user=replicator'
  trigger_file = '/tmp/postgresql.trigger'
  restore_command = 'cp /archive/%f %p'
```

## Testing Procedures
- Failover testing schedule
- Recovery time measurement
- Data integrity validation
- Communication plan testing
```

## Usage Guidelines

### When to Use Each Prompt

1. **Initial Analysis**: Start with initial_analysis_prompt.md
2. **Domain Deep Dive**: Use insurance/banking specialist prompts
3. **Technical Optimization**: Apply technical specialist prompts
4. **Integration Planning**: Use integration prompts
5. **Quality Assurance**: Apply data quality prompts
6. **Compliance**: Use regulatory specialist prompts
7. **Operations**: Apply DR/BC prompts

### Prompt Combination Strategies

```
For comprehensive modernization:
1. Initial Analysis
   +
2. Insurance Product Mapping (Domain)
   +
3. JSONB Optimization (Technical)
   +
4. Data Quality Framework (Quality)
   +
5. API Gateway Design (Integration)
   =
Complete Modernization Blueprint
```

### Customization Guidelines

- Replace placeholder values with actual system details
- Add domain-specific requirements
- Include regulatory requirements specific to jurisdiction
- Adjust technical stack to team expertise
- Scale complexity based on system size