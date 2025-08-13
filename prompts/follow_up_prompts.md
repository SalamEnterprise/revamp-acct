# Follow-Up Prompt Templates for Deep Dive Analysis

## 1. Performance Optimization Deep Dive

```
Based on the initial analysis of [function_name], perform a detailed performance optimization assessment:

## Current Performance Analysis
1. **Query Optimization**
   - Identify missing indexes on frequently queried columns
   - Find N+1 query problems in loops
   - Locate unnecessary JSON parsing operations
   - Identify opportunities for query consolidation

2. **Data Structure Optimization**
   - Analyze JSONB usage efficiency
   - Identify opportunities for denormalization
   - Suggest partitioning strategies for large tables
   - Recommend archival strategies for historical data

3. **Algorithm Improvements**
   - Replace sequential processing with set-based operations
   - Identify opportunities for parallel processing
   - Optimize string concatenation operations
   - Suggest caching strategies for static data

## Deliverables
- SQL script with CREATE INDEX statements
- Optimized function rewrites
- Performance benchmark estimates
- Implementation priority matrix
```

## 2. Data Quality and Validation Enhancement

```
Analyze the current data validation approach and propose comprehensive improvements:

## Validation Gap Analysis
1. **Input Validation**
   - Identify missing input parameter checks
   - Find potential SQL injection vulnerabilities
   - Locate unhandled NULL cases
   - Document data type mismatches

2. **Business Rule Validation**
   - Extract implicit business rules from code
   - Identify missing constraint checks
   - Find potential data integrity issues
   - Document edge cases not handled

3. **Output Validation**
   - Verify debit/credit balance checks
   - Validate transaction amount calculations
   - Check date range constraints
   - Ensure referential integrity

## Enhancement Proposals
- Validation framework design
- Error handling strategy
- Data quality monitoring approach
- Automated testing recommendations
```

## 3. Microservice Decomposition Analysis

```
Based on the monolithic function analysis, design a microservice architecture:

## Service Boundary Identification
1. **Domain Boundaries**
   - Identify bounded contexts using DDD principles
   - Map aggregate roots and entities
   - Define service responsibilities
   - Document inter-service dependencies

2. **Service Design**
   For each identified service:
   - Service name and purpose
   - API contract (OpenAPI specification)
   - Data ownership and storage
   - Event publishing/subscription
   - Synchronous vs asynchronous communication

3. **Transition Strategy**
   - Strangler fig pattern implementation
   - Service extraction sequence
   - Data migration approach
   - Dual-write strategy during transition

## Deliverables
- Service topology diagram
- API specifications for each service
- Event flow diagrams
- Migration roadmap with milestones
```

## 4. Event Sourcing Implementation Design

```
Transform the current state-based system to event-sourced architecture:

## Event Identification
1. **Domain Events**
   - Extract business events from current logic
   - Define event schemas and payloads
   - Identify event triggers and handlers
   - Map event sequences for each process

2. **Event Store Design**
   - Choose event store technology
   - Design event serialization format
   - Plan snapshot strategy
   - Define retention policies

3. **Projection Design**
   - Identify read models needed
   - Design projection update logic
   - Plan eventual consistency handling
   - Create materialized view strategies

## Implementation Details
- Event naming conventions
- Versioning strategy
- Replay mechanisms
- Compensation patterns for failures
```

## 5. Machine Learning Integration Analysis

```
Identify opportunities for ML/AI enhancement in the journal processing system:

## ML Opportunity Assessment
1. **Anomaly Detection**
   - Identify normal transaction patterns
   - Define anomaly indicators
   - Design feature extraction pipeline
   - Propose ML model architecture

2. **Predictive Analytics**
   - Forecast transaction volumes
   - Predict processing bottlenecks
   - Estimate error probability
   - Anticipate compliance issues

3. **Automated Classification**
   - Account code suggestion
   - Transaction categorization
   - Risk level assessment
   - Priority routing

## Technical Implementation
- Feature engineering approach
- Model training pipeline
- Real-time inference architecture
- Model monitoring and retraining
- A/B testing framework
```

## 6. Security and Compliance Hardening

```
Perform security assessment and propose hardening measures:

## Security Analysis
1. **Access Control**
   - Review current authentication/authorization
   - Identify privilege escalation risks
   - Propose RBAC/ABAC implementation
   - Design audit logging strategy

2. **Data Protection**
   - Identify sensitive data fields
   - Propose encryption strategies (at-rest, in-transit)
   - Design data masking for non-production
   - Plan key management approach

3. **Compliance Alignment**
   - Map to regulatory requirements (SOX, PCI-DSS, etc.)
   - Identify compliance gaps
   - Design compliance monitoring
   - Propose automated compliance checks

## Deliverables
- Security architecture diagram
- Compliance matrix
- Implementation checklist
- Penetration testing plan
```

## 7. Cloud Migration Strategy

```
Design a cloud migration strategy for the journal system:

## Cloud Readiness Assessment
1. **Current State Analysis**
   - Identify cloud-incompatible components
   - Assess data sovereignty requirements
   - Calculate data transfer volumes
   - Evaluate latency requirements

2. **Target Architecture**
   - Choose cloud provider and services
   - Design high availability architecture
   - Plan disaster recovery strategy
   - Define auto-scaling policies

3. **Migration Approach**
   - Lift-and-shift vs re-architecture decision
   - Hybrid cloud considerations
   - Data migration strategy
   - Cutover planning

## Cost Analysis
- Current vs cloud cost comparison
- Reserved vs on-demand pricing
- Cost optimization opportunities
- ROI calculation
```

## 8. Testing Strategy Development

```
Create comprehensive testing strategy for the modernized system:

## Test Coverage Analysis
1. **Unit Testing**
   - Identify testable units
   - Define coverage targets
   - Mock/stub strategy
   - Test data management

2. **Integration Testing**
   - Service integration points
   - Database integration tests
   - External system mocking
   - Contract testing approach

3. **Performance Testing**
   - Load testing scenarios
   - Stress testing thresholds
   - Capacity planning tests
   - Latency requirements

4. **Specialized Testing**
   - Chaos engineering approach
   - Security testing plan
   - Compliance validation tests
   - Disaster recovery testing

## Automation Strategy
- CI/CD pipeline design
- Test automation framework
- Test environment management
- Quality gates definition
```

## 9. Monitoring and Observability Design

```
Design comprehensive monitoring and observability solution:

## Observability Pillars
1. **Metrics**
   - Business metrics to track
   - Technical performance metrics
   - SLA/SLO definitions
   - Alert thresholds

2. **Logging**
   - Structured logging format
   - Log aggregation strategy
   - Log retention policies
   - Sensitive data handling

3. **Tracing**
   - Distributed tracing implementation
   - Trace sampling strategy
   - Critical path identification
   - Correlation ID propagation

## Implementation
- Technology stack selection
- Dashboard design
- Alert routing and escalation
- Incident response playbooks
```

## 10. Documentation and Knowledge Transfer

```
Create comprehensive documentation and knowledge transfer plan:

## Documentation Requirements
1. **Technical Documentation**
   - Architecture decision records (ADRs)
   - API documentation
   - Database schema documentation
   - Deployment guides

2. **Business Documentation**
   - Business process flows
   - User guides
   - Training materials
   - Troubleshooting guides

3. **Operational Documentation**
   - Runbooks
   - Incident response procedures
   - Maintenance schedules
   - Backup/recovery procedures

## Knowledge Transfer Plan
- Training sessions outline
- Hands-on workshops
- Documentation review cycles
- Competency assessment
```

## Meta-Prompt for Continuous Improvement

```
After implementing any modernization strategy, use this prompt for continuous improvement:

## Post-Implementation Review
1. **Performance Metrics**
   - Compare actual vs expected improvements
   - Identify unexpected bottlenecks
   - Measure user satisfaction
   - Calculate ROI achieved

2. **Lessons Learned**
   - What worked well?
   - What could be improved?
   - What was unexpected?
   - What would you do differently?

3. **Next Steps**
   - Identify optimization opportunities
   - Plan incremental improvements
   - Update documentation
   - Schedule follow-up reviews

## Continuous Improvement Cycle
- Establish KPIs and monitoring
- Regular performance reviews
- Quarterly optimization sprints
- Annual architecture reviews
```

## Prompt Chaining Strategy

```
For complex analysis, chain prompts in this sequence:

1. Initial Analysis (initial_analysis_prompt.md)
   ↓
2. Performance Deep Dive (if performance is critical)
   ↓
3. Architecture Selection (Microservices/CQRS/Event Sourcing)
   ↓
4. Security and Compliance Hardening
   ↓
5. Cloud Migration (if applicable)
   ↓
6. Testing Strategy
   ↓
7. Monitoring Design
   ↓
8. Documentation Plan
   ↓
9. Implementation Roadmap
   ↓
10. Post-Implementation Review

Each prompt builds on previous outputs for comprehensive analysis.
```