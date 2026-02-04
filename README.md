# NMC MVP - Database Models

This project implements the database schema for the NMC (Начальная Максимальная Цена) MVP system using SQLAlchemy and Alembic for migrations.

## Task 1: Define Database Models

Implemented the database schema as specified in requirement #6 of the requirements document.

### Database Tables

#### 1. `search_request`
Stores search requests with the following fields:
- `id` (UUID) - Primary key
- `created_at`, `updated_at` - Timestamps
- `status` (enum: RUNNING|DONE|STOPPED|ERROR) - Search status
- `input_source` (enum: MANUAL|FILE) - Source of search input
- `object_name` - Name of procurement object
- `ktru_code` - KTRU code
- `okpd2_code` - OKPD2 code (optional)
- `customer_region` - Customer region (default: СЗФО)
- `law` - Procurement law (default: 44)
- `date_from`, `date_to` - Date range for search
- `execution_statuses` (array) - Contract execution statuses
- `limit_contracts` - Limit of contracts to process (default: 30)
- `found_total` - Total contracts found on website
- `processed_count` - Number of contracts processed
- `nmc_value` - Calculated NMC value
- `selected_contract_ids` (array) - IDs of selected contracts for NMC calculation
- `runtime_ms` - Search runtime in milliseconds
- `error_message` - Error message if search failed
- `user_id` - User ID (for future authorization)
- `search_parameters_json` - Raw search parameters as JSON

#### 2. `contract_result`
Stores contract analysis results with the following fields:
- `id` (UUID) - Primary key
- `search_id` (UUID) - Foreign key to search_request
- `reestr_number` - Contract registry number
- `contract_url` - URL to contract card
- `sign_date` - Contract signing date
- `unit_price` - Price per unit (nullable)
- `currency` - Currency (default: RUB)
- `match_type` - Match type (IDENTICAL|HOMOGENEOUS|NO_MATCH)
- `ai_score` (0-100) - AI matching score
- `manufacturer_target` - Target manufacturer
- `manufacturer_found` - Found manufacturer
- `manufacturer_match` - Manufacturer match flag
- `is_2025_plus` - Flag for contracts from 2025+
- `accepted_for_nmc` - Flag if contract accepted for NMC calculation
- `raw_data_json` - Raw parsed contract data as JSON
- `contract_price` - Total contract price
- `customer_name` - Customer name
- `supplier_name` - Supplier name

#### 3. `spec_comparison_row`
Stores specification comparison details with the following fields:
- `id` (UUID) - Primary key
- `contract_result_id` (UUID) - Foreign key to contract_result
- `name` - Characteristic name
- `target_value` - Required value from TZ
- `actual_value` - Actual value from contract
- `match_status` (enum: MATCH|DIFF|UNKNOWN) - Match status
- `weight` - Importance weight (default: 1.0)
- `unit` - Unit of measurement
- `notes` - Additional notes

### Project Structure

```
.
├── src/nmc_mvp/
│   ├── config/
│   │   └── settings.py          # Application settings
│   ├── database/
│   │   └── database.py          # Database connection and session
│   └── models/
│       ├── __init__.py          # Model exports
│       ├── base.py              # Base model with common fields
│       ├── enums.py             # Enum definitions
│       ├── search_request.py    # SearchRequest model
│       ├── contract_result.py   # ContractResult model
│       └── spec_comparison_row.py # SpecComparisonRow model
├── alembic/                     # Alembic migrations
│   ├── versions/                # Migration scripts
│   ├── env.py                   # Alembic environment
│   └── script.py.mako           # Migration template
├── alembic.ini                  # Alembic configuration
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables
├── test_models.py              # Model test script
└── README.md                   # This file
```

### Installation and Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure database connection:**
   - Update `DATABASE_URL` in `.env` file
   - Or set environment variable: `export DATABASE_URL=postgresql://user:pass@host:port/dbname`

3. **Run database migrations:**
   ```bash
   # Create initial migration (already done)
   alembic revision --autogenerate -m "Initial migration"
   
   # Apply migrations
   alembic upgrade head
   ```

4. **Test the models:**
   ```bash
   python test_models.py
   ```

### Usage Examples

```python
from src.nmc_mvp.database.database import SessionLocal
from src.nmc_mvp.models import SearchRequest, ContractResult, SpecComparisonRow
from src.nmc_mvp.models.enums import SearchStatus, InputSource, MatchStatus
from datetime import datetime, timezone

# Create a database session
db = SessionLocal()

# Create a search request
search = SearchRequest(
    input_source=InputSource.MANUAL,
    object_name="Бумага офисная",
    ktru_code="24.11.11.110",
    date_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
    date_to=datetime(2026, 1, 1, tzinfo=timezone.utc),
    status=SearchStatus.RUNNING
)

# Create a contract result
contract = ContractResult(
    search_id=search.id,
    reestr_number="0373200004523000010",
    contract_url="https://zakupki.gov.ru/...",
    sign_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
    match_type="IDENTICAL",
    ai_score=95,
    accepted_for_nmc=True
)

# Create specification comparison
spec = SpecComparisonRow(
    contract_result_id=contract.id,
    name="Плотность",
    target_value="80 г/м²",
    actual_value="80 г/м²",
    match_status=MatchStatus.MATCH
)

# Save to database
db.add(search)
db.add(contract)
db.add(spec)
db.commit()
```

### Migration Commands

- **Create new migration:** `alembic revision --autogenerate -m "Description"`
- **Apply migrations:** `alembic upgrade head`
- **Rollback migration:** `alembic downgrade -1`
- **Show migration history:** `alembic history`
- **Show current revision:** `alembic current`

### Dependencies

- SQLAlchemy 2.0.25 - ORM for database operations
- Alembic 1.13.1 - Database migration tool
- psycopg2-binary 2.9.9 - PostgreSQL adapter
- python-dotenv 1.0.0 - Environment variable management
- pydantic 2.5.3 - Data validation
- uuid - UUID generation

### Notes

- The schema uses PostgreSQL-specific features (UUID, ARRAY, JSON, ENUM types)
- All tables include automatic `created_at` and `updated_at` timestamps
- Foreign key relationships are properly configured with cascading deletes
- Indexes are created for frequently queried fields
- The migration script includes proper creation/dropping of enum types