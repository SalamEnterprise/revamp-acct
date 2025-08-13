# Initial Analysis Prompt for Legacy System Modernization

## Primary Prompt Template

```
You are an expert system architect and code analyst specializing in legacy system modernization and financial/insurance domain systems. Your task is to perform a comprehensive analysis of a legacy accounting/journal processing system.

## Context
- System Type: [Insurance/Banking/Financial] Journal Processing System
- Current Stack: PostgreSQL stored procedures with PL/pgSQL functions
- Target Output: CSV files for external accounting system integration (e.g., SUN Accounting System)
- Domain: Financial transaction journaling with audit requirements

## Analysis Requirements

### Phase 1: Code Extraction and Documentation
1. **Function Analysis**
   - Read and extract the main function: [function_name(parameters)]
   - Identify ALL dependent functions called within the main function
   - Document function signatures, parameters, and return types
   - Save each function in a structured format under `/fns` directory

2. **Database Schema Discovery**
   - Extract all table names referenced in the functions (typically after FROM, INSERT INTO, UPDATE statements)
   - Identify table relationships and foreign keys
   - Document field names and data types
   - Map JOIN conditions and WHERE clause relationships
   - Save table documentation under `/tbls` directory

3. **Data Flow Mapping**
   - Trace data flow from source tables through transformations to output
   - Identify JSONB field usage and structure
   - Document array manipulations and string concatenations
   - Map transaction codes (T1-T10) and their business meanings

### Phase 2: Business Logic Analysis
1. **Business Rules Extraction**
   - Identify validation rules and constraints
   - Document conditional logic and business decisions
   - Extract account code patterns and mappings
   - Identify date-based processing rules

2. **Process Flow Documentation**
   - Create high-level pseudo code representing the business logic
   - Document the journal entry creation process
   - Map voucher consolidation logic
   - Identify GL (General Ledger) posting rules

3. **Audit and Compliance Requirements**
   - Document traceability requirements
   - Identify immutability needs
   - Extract error handling and rollback logic
   - Map regulatory compliance touchpoints

### Phase 3: Enhancement Strategy Development
1. **Current System Assessment**
   - Performance bottlenecks (loops, JSON parsing, string operations)
   - Maintainability issues (monolithic functions, embedded logic)
   - Scalability limitations
   - Technical debt identification

2. **Modernization Approaches**
   Create at least 6 different strategic approaches considering:
   - Performance optimization strategies
   - Architecture patterns (Microservices, CQRS, Event Sourcing, etc.)
   - Technology stack options (cloud-native, on-premise, hybrid)
   - Database alternatives (Graph, Time-series, Blockchain)
   - Processing paradigms (batch, stream, real-time)
   - ML/AI integration opportunities

3. **Implementation Roadmap**
   For each approach, provide:
   - Technology stack details
   - Architecture diagrams (in ASCII or markdown format)
   - Implementation phases with timelines
   - Risk assessment and mitigation strategies
   - Cost-benefit analysis
   - Expected performance improvements

## Output Structure

Create the following directory structure:
```
/fns           # Extracted functions with comments
/tbls          # Table schemas and relationships  
/plans         # Business logic analysis and strategies
/prompts       # Prompt templates for future analysis
```

## Special Considerations

1. **JSONB Processing**: Pay special attention to JSONB field manipulation as it often contains critical business data
2. **Account Patterns**: Look for keyword-based account routing (BANK, PREMI, PIUTANG, etc.)
3. **Transaction Codes**: Document T1-T10 analysis dimensions and their business context
4. **Audit Trail**: Ensure all proposals maintain or enhance audit capabilities
5. **Zero Downtime**: Consider migration strategies that allow parallel running

## Constraints
- NEVER hallucinate table names, field names, or function names
- ONLY use actual database objects discovered during analysis
- Permission to add indexes and relations for performance
- Permission to create new tables if justified by business needs

## Deliverables
1. Complete function documentation
2. Database schema analysis
3. Business logic pseudo code
4. At least 6 modernization strategies
5. Evaluation matrix comparing all approaches
6. Recommended implementation path with justification
```

## Enhanced Analysis Questions

Before starting the analysis, gather this information:
1. What is the primary business domain? (Insurance/Banking/Financial Services)
2. What is the current transaction volume per day?
3. What are the critical compliance requirements?
4. What is the acceptable downtime window?
5. What is the team's technical expertise level?
6. What is the budget range for modernization?
7. Are there any specific pain points to prioritize?

## Analysis Execution Commands

```bash
# PostgreSQL function extraction
psql -U [user] -d [database] -c "\sf function_name"
psql -U [user] -d [database] -c "\df function_pattern*"
psql -U [user] -d [database] -c "\d+ table_name"

# Dependency analysis
psql -U [user] -d [database] -c "
SELECT distinct 
    n.nspname as schema,
    p.proname as function,
    pg_get_function_identity_arguments(p.oid) as arguments
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE p.prosrc LIKE '%search_pattern%'
"
```

## Success Criteria
- All functions documented with clear purpose and parameters
- Complete data flow from source to CSV output mapped
- Business rules extracted and validated
- At least 6 viable modernization strategies proposed
- Clear recommendation with implementation roadmap
- Comprehensive risk assessment completed