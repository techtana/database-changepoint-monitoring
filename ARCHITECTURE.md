# Multi-Database Changepoint Monitoring Architecture

## Overview

The codebase has been refactored to support multiple database backends (Snowflake, BigQuery, SQLite) through an abstract database adapter pattern. The core change-detection logic remains database-agnostic and reusable.

## Architecture

### Directory Structure

```
database_changepoint_monitoring/
├── databases/                 # Database adapter implementations
│   ├── __init__.py           # Factory function: get_adapter()
│   ├── base.py               # Abstract DatabaseAdapter interface
│   ├── snowflake.py          # Snowflake implementation
│   ├── bigquery.py           # BigQuery implementation
│   └── sqlite.py             # SQLite implementation
├── core/                      # Database-agnostic changepoint logic
│   ├── __init__.py
│   ├── snapshot.py           # Snapshot read/write operations
│   └── changelog.py          # Changelog write operations
├── comparator.py             # Pure diff algorithm (unchanged)
├── monitor.py                # Main orchestrator
├── config.yaml               # Configuration with DB type selection
├── requirements.txt          # Dependencies (with optional DB drivers)
└── test_refactoring.py       # Test suite for adapters
```

### Design Pattern: Database Adapter

All database interactions go through the `DatabaseAdapter` interface (`databases/base.py`). Each database type implements this interface:

```python
class DatabaseAdapter(ABC):
    def connect()                           # Establish connection
    def close()                             # Close connection
    def execute_query(sql, params) -> list  # SELECT query
    def execute_many(sql, rows_list)        # Bulk INSERT
    def get_support_tables_ddl(...)         # Return CREATE TABLE DDL
    def parse_json_column(col_name) -> str  # JSON parsing function
    def json_constructor(value_expr) -> str # JSON value constructor
```

**Key insight**: Each database handles SQL/type differences internally. The core logic (`snapshot.py`, `changelog.py`) uses generic placeholders (`?`) and delegates database-specific formatting to the adapter.

---

## Configuration

### New Config Format

Edit `config.yaml` to select database type and provide credentials:

```yaml
database:
  type: "snowflake"  # Choose: snowflake, bigquery, or sqlite

  # For Snowflake:
  snowflake:
    account:   "${SNOWFLAKE_ACCOUNT}"
    user:      "${SNOWFLAKE_USER}"
    password:  "${SNOWFLAKE_PASSWORD}"
    warehouse: "${SNOWFLAKE_WAREHOUSE}"
    database:  "${SNOWFLAKE_DATABASE}"
    role:      "${SNOWFLAKE_ROLE}"

  # For BigQuery:
  bigquery:
    project: "${GCP_PROJECT}"
    dataset: "${GCP_DATASET}"
    credentials_path: "/path/to/service-account.json"  # optional

  # For SQLite:
  sqlite:
    path: "./changepoint.db"  # File-based or ":memory:" for in-memory

monitoring:
  snapshot_table: "MYDB.MONITORING.DAILY_SNAPSHOTS"
  changelog_table: "MYDB.MONITORING.CHANGE_LOG"

tables:
  - name: "MYDB.CONFIG.TABLE_A"
    pk_columns: [pk1, pk2]
    value_columns: [val1, val2]
```

**Environment Variable Substitution**: Any config value wrapped in `${VAR}` is replaced with the environment variable value.

---

## Database-Specific Setup

### Snowflake

**Installation**:
```bash
pip install -r requirements.txt
# or
pip install snowflake-connector-python>=3.6.0
```

**Configuration**:
1. Set environment variables or add to `.env`:
   ```
   SNOWFLAKE_ACCOUNT=xy12345.us-east-1
   SNOWFLAKE_USER=monitor_user
   SNOWFLAKE_PASSWORD=secret
   SNOWFLAKE_WAREHOUSE=COMPUTE_WH
   SNOWFLAKE_DATABASE=MYDB
   SNOWFLAKE_ROLE=MONITOR_ROLE
   ```

2. Edit `config.yaml`:
   ```yaml
   database:
     type: "snowflake"
     snowflake:
       account:   "${SNOWFLAKE_ACCOUNT}"
       user:      "${SNOWFLAKE_USER}"
       password:  "${SNOWFLAKE_PASSWORD}"
       warehouse: "${SNOWFLAKE_WAREHOUSE}"
       database:  "${SNOWFLAKE_DATABASE}"
       role:      "${SNOWFLAKE_ROLE}"
   ```

3. Run:
   ```bash
   python monitor.py
   ```

### BigQuery

**Installation**:
```bash
pip install google-cloud-bigquery>=3.11.0
```

**Configuration**:
1. Set up Google Cloud credentials. BigQuery will auto-detect from:
   - `GOOGLE_APPLICATION_CREDENTIALS` environment variable
   - Default credentials (if running on GCP)
   - Or pass `credentials_path` in config

2. Edit `config.yaml`:
   ```yaml
   database:
     type: "bigquery"
     bigquery:
       project: "my-gcp-project"
       dataset: "monitoring"
       # credentials_path: "/path/to/service-account.json"  # optional
   ```

3. Run:
   ```bash
   python monitor.py
   ```

### SQLite (Local Testing)

**No additional installation needed** — SQLite is built into Python.

**Configuration**:
1. Edit `config.yaml`:
   ```yaml
   database:
     type: "sqlite"
     sqlite:
       path: "./changepoint.db"  # or ":memory:" for in-memory
   ```

2. Create test tables in the source:
   ```bash
   sqlite3 changepoint.db "CREATE TABLE CONFIG_TABLE_A (id TEXT PRIMARY KEY, config_value TEXT)"
   ```

3. Run:
   ```bash
   python monitor.py config.yaml
   ```

---

## Adding a New Database Type

To support a new database (PostgreSQL, MySQL, etc.):

1. **Create a new adapter file** (`databases/postgres.py`):
   ```python
   from .base import DatabaseAdapter
   import psycopg2

   class PostgresAdapter(DatabaseAdapter):
       def __init__(self, config: dict):
           self.config = config
           self.connection = None

       def connect(self):
           self.connection = psycopg2.connect(
               host=self.config["host"],
               user=self.config["user"],
               password=self.config["password"],
               database=self.config["database"],
           )
           return self

       def close(self):
           if self.connection:
               self.connection.close()

       def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
           # PostgreSQL uses %s for parameters
           cursor = self.connection.cursor()
           cursor.execute(sql, params)
           cols = [desc[0] for desc in cursor.description]
           return [dict(zip(cols, row)) for row in cursor.fetchall()]

       def execute_many(self, sql: str, rows: list[tuple]) -> None:
           cursor = self.connection.cursor()
           cursor.executemany(sql, rows)
           self.connection.commit()

       def get_support_tables_ddl(self, snapshot_table, changelog_table) -> tuple:
           # Return PostgreSQL-specific DDL
           snapshot_ddl = f"""
               CREATE TABLE IF NOT EXISTS {snapshot_table} (
                   snapshot_date DATE NOT NULL,
                   table_name VARCHAR(255) NOT NULL,
                   pk_json JSONB NOT NULL,
                   values_json JSONB NOT NULL
               )
           """
           # Similar for changelog_ddl...
           return snapshot_ddl, changelog_ddl

       def parse_json_column(self, col_name: str) -> str:
           return col_name  # PostgreSQL JSONB doesn't need parsing

       def json_constructor(self, value_expr: str) -> str:
           return f"{value_expr}::jsonb"
   ```

2. **Update the factory** (`databases/__init__.py`):
   ```python
   elif db_type == "postgres":
       from .postgres import PostgresAdapter
       return PostgresAdapter(config)
   ```

3. **Update `config.yaml`**:
   ```yaml
   database:
     type: "postgres"
     postgres:
       host: "localhost"
       user: "monitor"
       password: "${DB_PASSWORD}"
       database: "monitoring"
   ```

4. **Update `requirements.txt`**:
   ```
   psycopg2-binary>=2.9.0 ; extra == "postgres"
   ```

---

## Testing

### Run the Provided Test Suite

```bash
python test_refactoring.py
```

This test:
- Creates an in-memory SQLite database
- Creates support tables
- Inserts test data
- Takes a snapshot
- Detects changes
- Writes to the changelog
- Verifies round-trip integrity

### Test with Your Database

1. Copy and edit the config:
   ```bash
   cp config.yaml config.test.yaml
   # Edit config.test.yaml with test credentials
   ```

2. Run:
   ```bash
   python monitor.py config.test.yaml
   ```

3. Verify tables were created and records written:
   - **Snowflake**: `SELECT * FROM MYDB.MONITORING.DAILY_SNAPSHOTS;`
   - **BigQuery**: `SELECT * FROM monitoring.DAILY_SNAPSHOTS;`
   - **SQLite**: `sqlite3 changepoint.db "SELECT * FROM DAILY_SNAPSHOTS;"`

---

## Column Naming Across Databases

Different databases return column names in different cases:
- **Snowflake**: UPPERCASE
- **BigQuery**: lowercase (or as-is from schema)
- **SQLite**: lowercase (or as-is from CREATE TABLE)

**The solution**: The `_normalize_row_keys()` function in `core/snapshot.py` converts all keys to UPPERCASE before processing, ensuring consistent behavior across databases.

---

## Backward Compatibility

Existing Snowflake deployments work unchanged. To migrate:

1. Ensure `config.yaml` has:
   ```yaml
   database:
     type: "snowflake"
     snowflake:
       # Your existing environment variables
   ```

2. Run `monitor.py` as before:
   ```bash
   python monitor.py
   ```

The behavior and output are identical to the original single-database version.

---

## Dependencies by Database Type

| Database | Required Package | Installation |
|----------|------------------|--------------|
| SQLite   | (built-in)       | None         |
| Snowflake | `snowflake-connector-python` | `pip install -r requirements.txt` or `pip install 'snowflake-connector-python>=3.6.0'` |
| BigQuery | `google-cloud-bigquery` | `pip install 'google-cloud-bigquery>=3.11.0'` |

**Minimal install** (SQLite only):
```bash
pip install PyYAML python-dotenv
```

**With Snowflake**:
```bash
pip install -r requirements.txt
```

**With BigQuery**:
```bash
pip install PyYAML python-dotenv 'google-cloud-bigquery>=3.11.0'
```

---

## Query Examples for Each Database

### Get all changes on a specific day

**Snowflake**:
```sql
SELECT * FROM MYDB.MONITORING.CHANGE_LOG
WHERE change_date = '2026-05-02'
ORDER BY table_name, pk_json, column_name;
```

**BigQuery**:
```sql
SELECT * FROM my_project.monitoring.CHANGE_LOG
WHERE change_date = '2026-05-02'
ORDER BY table_name, pk_json, column_name;
```

**SQLite**:
```sql
SELECT * FROM CHANGE_LOG
WHERE change_date = '2026-05-02'
ORDER BY table_name, pk_json, column_name;
```

### Get history of a specific config row

**Snowflake**:
```sql
SELECT * FROM MYDB.MONITORING.CHANGE_LOG
WHERE table_name = 'MYDB.CONFIG.TABLE_A'
  AND JSON_EXTRACT_PATH_TEXT(pk_json, 'pk1') = 'value1'
ORDER BY change_date;
```

**BigQuery**:
```sql
SELECT * FROM my_project.monitoring.CHANGE_LOG
WHERE table_name = 'MYDB.CONFIG.TABLE_A'
  AND JSON_EXTRACT_SCALAR(pk_json, '$.pk1') = 'value1'
ORDER BY change_date;
```

**SQLite**:
```sql
SELECT * FROM CHANGE_LOG
WHERE table_name = 'CONFIG_TABLE_A'
  AND json_extract(pk_json, '$.pk1') = 'value1'
ORDER BY change_date;
```

---

## Performance Considerations

- **Snowflake**: Optimized for large tables; VARIANT columns efficient for JSON
- **BigQuery**: Excellent for analytical queries over change history; pay-as-you-go pricing
- **SQLite**: Best for small-to-medium tables, local development, and testing

For production use, adjust table-naming conventions and retention policies per your database's best practices.
