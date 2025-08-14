# Initial Journal System Analysis Prompt

## Objective
Analyze and understand the PostgreSQL function `fn_insert_sun_journal` for insurance journal processing system.

## Task Requirements

### 1. Function Extraction
- Extract the main function `fn_insert_sun_journal(date, integer)`
- Identify and extract all dependent functions
- Document the function hierarchy and dependencies

### 2. Documentation Structure
Create organized folders:
```
/fns/     - All extracted functions
/tbls/    - Table structures and relationships
/plans/   - Enhancement strategies
/prompts/ - Reusable analysis prompts
```

### 3. Analysis Requirements
- **Business Logic**: Document the journal creation process
- **Data Flow**: Map data sources to journal entries
- **Performance**: Identify bottlenecks and optimization opportunities
- **Dependencies**: List all tables, functions, and external dependencies

### 4. Deliverables
- Pseudo code representation
- Business logic documentation
- Enhancement strategies with pros/cons
- Performance optimization recommendations

## Expected Output Format

### Function Documentation
```sql
-- Function: fn_insert_sun_journal
-- Purpose: [Description]
-- Parameters: 
--   p_journal_date: Processing date
--   p_created_by: User ID
-- Returns: Status code
-- Dependencies: [List of functions/tables]
```

### Enhancement Strategies
1. **Approach 1**: Modernize with Python
   - Pros: [List advantages]
   - Cons: [List disadvantages]
   - Effort: [Time estimate]

2. **Approach 2**: Enhanced PostgreSQL
   - Pros: [List advantages]
   - Cons: [List disadvantages]
   - Effort: [Time estimate]

## Sample Command
```bash
# Analyze the function
psql -d database_name -c "\df+ fn_insert_sun_journal"

# Extract dependencies
SELECT proname, prosrc 
FROM pg_proc 
WHERE prosrc LIKE '%fn_insert_sun_journal%';
```

## Success Criteria
- Complete function extraction
- Clear documentation
- Actionable enhancement strategies
- Performance baseline established