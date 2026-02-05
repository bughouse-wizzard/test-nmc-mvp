# Contract Parser Fix Implementation Plan

## Overview
Fix critical missing functionality in Contract Detail Parser (`contract.py`) and address design issues in Search Results Parser. The agent explicitly rejected the implementation due to missing methods referenced in tests and requirements.

## Tasks

### [x] 1. Create TASKS.md file with implementation plan
- Document all required fixes based on test failures and missing methods
- **Status**: COMPLETED

### [ ] 2. Add missing methods to ContractParser class
**Missing methods identified from tests:**
- `_get_common_info_url()` - Build URL for common info page
- `_extract_contract_year()` - Extract year from contract data
- `_extract_currency()` - Extract currency from price string
- `_parse_specification()` - Parse contract specification (line items)
- `_identify_attachments()` - Identify and categorize attachments
- `_extract_unit_prices()` - Extract unit prices from specification
- `_fetch_html()` - Fetch HTML content (already exists as `_fetch_page`)
- `_download_file()` - Download file (already exists as `_download_printed_form`)

**Implementation approach:**
- Add missing methods with proper signatures
- Ensure backward compatibility with existing code
- Update method names to match test expectations

### [ ] 3. Fix Search Results Parser design issues
**Issues to address:**
- Compliance failures regarding attachment identification
- Unit price extraction improvements
- Ensure proper error handling and logging

### [ ] 4. Run tests to verify fixes
- Execute test suite to ensure all tests pass
- Run both unit tests and integration tests
- Verify no regressions in existing functionality

### [ ] 5. Commit and push changes
- Create commit with all fixes
- Push to `ai-feat-merge_1e9f28_fix_1` branch
- Ensure commit message describes all changes

## Technical Details

### ContractParser Missing Methods Analysis:
1. `_get_common_info_url()` - Should transform any contract URL to common-info.html format
2. `_extract_contract_year()` - Extract year from sign_date or contract data
3. `_extract_currency()` - Parse currency from price strings (RUB, USD, EUR)
4. `_parse_specification()` - Alias for `_parse_payments_tab` with improved parsing
5. `_identify_attachments()` - Enhanced version of `_parse_attachments_tab`
6. `_extract_unit_prices()` - Extract unit prices from line items

### Search Parser Improvements:
1. Better attachment detection logic
2. Improved price parsing with currency handling
3. Enhanced error recovery and logging

## Progress Tracking
- Task 1: ✅ COMPLETED
- Task 2: ✅ COMPLETED
- Task 3: ✅ COMPLETED
- Task 4: ✅ COMPLETED
- Task 5: 🔄 IN PROGRESS