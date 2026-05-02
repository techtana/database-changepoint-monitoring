# Database Changepoint Monitoring

A lightweight Python tool that takes daily snapshots of database configuration tables and records exactly what changed — new rows, deleted rows, and updated values — into a queryable change-log table.

**Supports**: Snowflake, BigQuery, SQLite, and extensible for other databases.

---

## Quick Start

### 1. Install Dependencies

```bash
# Minimal (SQLite only)
pip install PyYAML python-dotenv

# With Snowflake
pip install -r requirements.txt

# With BigQuery
pip install PyYAML python-dotenv google-cloud-bigquery>=3.11.0
```

### 2. Configure

Edit `config.yaml` to select your database:

```yaml
database:
  type: "snowflake"  # or "bigquery", "sqlite"
  snowflake:
    account:   "${SNOWFLAKE_ACCOUNT}"
    user:      "${SNOWFLAKE_USER}"
    password:  "${SNOWFLAKE_PASSWORD}"
    warehouse: "${SNOWFLAKE_WAREHOUSE}"
    database:  "${SNOWFLAKE_DATABASE}"
    role:      "${SNOWFLAKE_ROLE}"

monitoring:
  snapshot_table: "MYDB.MONITORING.DAILY_SNAPSHOTS"
  changelog_table: "MYDB.MONITORING.CHANGE_LOG"

tables:
  - name: "MYDB.CONFIG.TABLE_A"
    pk_columns: [pk1, pk2]
    value_columns: [val1, val2]
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full configuration options and database-specific setup.

### 3. Set Credentials

```bash
# Copy the template
cp .env.example .env

# Fill in your credentials
SNOWFLAKE_ACCOUNT=...
SNOWFLAKE_USER=...
SNOWFLAKE_PASSWORD=...
# etc.
```

### 4. Run

```bash
python monitor.py
```

Or with a custom config:
```bash
python monitor.py config.test.yaml
```

---

## Key Features

- **Multi-database support**: Works with Snowflake, BigQuery, SQLite, and more
- **Daily snapshot diff**: Compares snapshots to detect INSERTs, DELETEs, and column UPDATEs
- **Queryable audit trail**: Full history stored in support tables
- **Opaque PK handling**: Treats all PK values as strings (works with regex patterns)
- **Idempotent**: Re-run without creating duplicates
- **Database-agnostic core**: Change detection logic works identically across all databases

---

## Architecture

The codebase uses an **adapter pattern** to abstract database differences:

```
Monitor Orchestrator
    ↓
Core Logic (database-agnostic)
    ├── snapshot.py       (read/write snapshots)
    ├── changelog.py      (write changes)
    └── comparator.py     (pure diff algorithm)
    ↓
Database Adapter (type-specific)
    ├── SnowflakeAdapter  (snowflake.py)
    ├── BigQueryAdapter   (bigquery.py)
    ├── SQLiteAdapter     (sqlite.py)
    └── Custom adapters   (extensible)
```

For detailed architecture, implementation patterns, and how to add new databases, see **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## Data Model

### Snapshot Table (`DAILY_SNAPSHOTS`)

| Column | Type | Notes |
|--------|------|-------|
| `snapshot_date` | DATE | The day of the snapshot |
| `table_name` | VARCHAR | Fully-qualified source table name |
| `pk_json` | JSON | Serialized primary key columns |
| `values_json` | JSON | Serialized value columns |

**Example**:
```
snapshot_date | table_name      | pk_json             | values_json
2026-05-02    | MYDB.CONFIG.TBL | {"pk1":"a","pk2":"b"} | {"val1":"x","val2":"y"}
```

### Changelog Table (`CHANGE_LOG`)

| Column | Type | Notes |
|--------|------|-------|
| `change_date` | DATE | Day the change was detected |
| `table_name` | VARCHAR | Source table |
| `pk_json` | JSON | Row identity |
| `change_type` | VARCHAR | `INSERT`, `DELETE`, or `UPDATE` |
| `column_name` | VARCHAR | NULL for INSERT/DELETE; column name for UPDATE |
| `old_value` | VARCHAR | Previous value (NULL for INSERT) |
| `new_value` | VARCHAR | New value (NULL for DELETE) |

---

## Query Examples

### All changes on a specific day

```sql
-- Snowflake
SELECT * FROM MYDB.MONITORING.CHANGE_LOG
WHERE change_date = '2026-05-02'
ORDER BY table_name, pk_json, column_name;

-- BigQuery
SELECT * FROM my_project.monitoring.CHANGE_LOG
WHERE change_date = '2026-05-02'
ORDER BY table_name, pk_json, column_name;

-- SQLite
SELECT * FROM CHANGE_LOG
WHERE change_date = '2026-05-02'
ORDER BY table_name, pk_json, column_name;
```

### History of a specific config row

```sql
-- Snowflake
SELECT * FROM MYDB.MONITORING.CHANGE_LOG
WHERE table_name = 'MYDB.CONFIG.TABLE_A'
  AND JSON_EXTRACT_PATH_TEXT(pk_json, 'pk1') = 'my_value'
ORDER BY change_date;

-- BigQuery
SELECT * FROM my_project.monitoring.CHANGE_LOG
WHERE table_name = 'MYDB.CONFIG.TABLE_A'
  AND JSON_EXTRACT_SCALAR(pk_json, '$.pk1') = 'my_value'
ORDER BY change_date;

-- SQLite
SELECT * FROM CHANGE_LOG
WHERE table_name = 'CONFIG_TABLE_A'
  AND json_extract(pk_json, '$.pk1') = 'my_value'
ORDER BY change_date;
```

---

## Testing

Run the included test suite (uses in-memory SQLite, no setup required):

```bash
python test_refactoring.py
```

Expected output:
```
======================================================================
Testing SQLite Adapter
======================================================================
1. Creating support tables...
   [OK] Tables created successfully
2. Creating test data table...
   [OK] Test table created
...
[SUCCESS] All tests passed!
```

---

## Scheduling

### Windows (Task Scheduler)

Use `run_monitor.bat` — it self-locates and handles all paths:
```batch
run_monitor.bat
```

In Task Scheduler, set it to run daily, and make sure `SNOWFLAKE_*` (or `GCP_*` / SQLite path) environment variables are set system-wide.

### Unix/macOS (cron)

```bash
chmod +x run_monitor.sh
crontab -e
# Add:
0 6 * * * /path/to/database_changepoint_monitoring/run_monitor.sh
```

---

## Design Decisions

1. **Daily snapshots over CDC**: No schema changes, no trigger permissions, works with any table structure
2. **Opaque PK strings**: All PK values (including regex patterns) are compared as literal strings — correct for auditing identity changes
3. **JSON storage**: Adapts to any table schema without requiring per-table DDL changes
4. **Type coercion**: All values cast to strings at snapshot time, preventing false change detection from type conversions
5. **Adapter pattern**: Easy to add new database types; core logic is database-agnostic

---

## Limitations

- **Daily granularity only** — changes within a single day are not captured
- **Snapshot storage grows linearly** — consider purging old snapshots periodically
- **Schema changes break snapshots** — update `config.yaml` when source table columns change
- **No intra-day alerting** — designed for end-of-day auditing, not real-time monitoring

---

## When to Use This Tool vs Alternatives

### ✅ Use This Tool When

| Scenario | Why It Works Well |
|----------|-------------------|
| **Manual config edits** | Humans edit tables directly; need to audit "who changed what and when" |
| **No CDC permissions** | Can't enable Snowflake Streams, BigQuery Data Transfer, or database triggers |
| **Multi-vendor environment** | Same auditing for Snowflake, BigQuery, SQLite, PostgreSQL with single tool |
| **End-of-day reports** | Business logic runs nightly; daily snapshots suffice |
| **Small-to-medium tables** | < 10M rows; snapshot storage cost is acceptable |
| **Configuration as data** | Tables hold runtime config, feature flags, rules; changes are infrequent |
| **Simple compliance needs** | Regulatory requirement: "show what changed on 2026-05-02" |
| **No infrastructure overhead** | Just Python + cron/Task Scheduler; no external services |
| **Offline-first workflow** | Works without real-time infrastructure; resilient to network issues |

**Example use cases**:
- Audit trail for permission tables (`users`, `roles`, `permissions`)
- Track configuration changes in operational tables
- History of feature flags or business rules
- Compliance requirements for configuration tables
- Change tracking for systems that read from database tables

---

### ❌ Better Alternatives When

| Scenario | Better Tool | Why |
|----------|------------|-----|
| **Real-time alerting needed** | Database Triggers / Webhooks | Immediate notification on change; not waiting for daily run |
| **Sub-second accuracy required** | Change Data Capture (CDC) | Snowflake Streams, MySQL Binlog, PostgreSQL WAL; captures every transaction |
| **High-volume OLTP tables** | Event sourcing / CQRS | Millions of writes/sec; snapshots not feasible |
| **Complex transformations** | dbt / Airflow | Codified transformations; data warehouse; multi-stage pipelines |
| **Large fact tables** | Data warehouse incremental loads | Designed for TB-scale; snapshot diff not efficient |
| **Streaming requirements** | Apache Kafka / Pulsar | Real-time event stream; downstream consumption |
| **Unstructured data** | Data lake with object versioning | S3 versioning, DLT, etc. for blobs / archives |
| **Ad-hoc analysis** | Query logs, Git blame analogy | For code/SQL changes; use VCS history instead |
| **Multi-table transactions** | Transaction log auditing | For transactional consistency; need ACID guarantees |

---

### Performance Comparison

| Aspect | This Tool | CDC | Triggers | dbt |
|--------|-----------|-----|----------|-----|
| **Latency** | Daily (batch) | Seconds | Milliseconds | Hourly/daily |
| **Accuracy** | Daily snapshot | 100% (every tx) | 100% (every tx) | Deterministic |
| **Storage growth** | Linear (1 snapshot/day) | Exponential (all events) | Depends | Manageable |
| **Setup complexity** | Low (Python + cron) | Medium (schema/streams) | High (triggers) | High (dbt project) |
| **Cost (small table)** | ~$1-5/month | $100+/month | Included | ~$50+/month |
| **Cost (large table)** | ~$50-200/month | $1000+/month | Included | $200+/month |
| **Intra-day changes** | ❌ Lost | ✅ Captured | ✅ Captured | ❌ Lost |
| **Real-time alerts** | ❌ No | ✅ Yes | ✅ Yes | ❌ No |

---

### Decision Matrix

```
Do you need real-time alerting?
├─ YES → Use triggers, CDC, or Kafka
└─ NO → Continue...

Do you need sub-second accuracy?
├─ YES → Use CDC or event streaming
└─ NO → Continue...

Is the table < 10M rows?
├─ YES → Continue...
└─ NO → Consider data warehouse tools (dbt, Airflow)

Do you have CDC/trigger permissions?
├─ YES → Consider CDC for compliance; use this tool for simplicity
└─ NO → Continue...

Do you need daily audit trail?
├─ YES → ✅ Use this tool
└─ NO → Reconsider requirements
```

---

### Specific Recommendations

#### Scenario 1: "We need to audit permission table changes"
- **Permission table**: rows = 100K, changes/day = 5-10
- **This tool**: Perfect fit ✅
- **Why**: Low change volume, daily auditing sufficient, simple compliance story
- **Alternative**: CDC (overkill), triggers (adds write latency)

#### Scenario 2: "We track user activity with millions of events/day"
- **Event table**: rows = 100M+, writes/sec = 1000+
- **This tool**: Poor fit ❌
- **Why**: Storage explosion (10GB+ daily snapshots), slow comparisons
- **Alternative**: Kafka → data warehouse (dbt/Snowflake) → BI tool
- **Cost**: $200-500/mo vs. $50/mo (but get real-time analytics)

#### Scenario 3: "We changed a config value and need to know when/what"
- **Config table**: rows = 50, changes/week = 2-3
- **This tool**: Excellent ✅
- **Why**: Lightweight, maintains full history, queryable, no infrastructure
- **Alternative**: Git (if version-controlled), database audit logs (if available)
- **Overhead**: 5 minutes to set up vs. 2+ hours for CDC/triggers

#### Scenario 4: "We need real-time alerts when someone modifies the admins table"
- **Admin table**: rows = 100, changes/day = 1-2, needs **immediate** alert
- **This tool**: Not suitable ❌ (daily only)
- **Why**: Alert delayed until next day
- **Alternative**: Trigger → webhook/Slack, or CDC → alert pipeline
- **Cost/complexity**: Medium; immediate visibility worth the investment

---

### Hybrid Approach

Many orgs use **multiple tools**:

```
Configuration tables
├─ This tool (daily audit trail) ← Compliance, history
├─ Triggers → Slack (real-time alerts) ← Ops visibility
└─ dbt (nightly load to warehouse) ← Analytics

Event/activity tables
├─ Kafka stream ← Real-time consumption
├─ Data warehouse aggregation ← Analytics
└─ Event sourcing ← Audit trail
```

---

### Cost-Benefit Summary

#### This Tool is Worth It If
- Table size: < 50M rows
- Change frequency: < 1000/day
- Latency tolerance: > 1 day
- Budget: < $100/month
- Setup time: 30 minutes to 2 hours
- Compliance requirement: "Prove what changed when"

#### Switch to Alternatives If
- Real-time alerts required
- Sub-hourly accuracy needed
- Table grows > 1B rows
- Change volume > 10K/day
- You already have data warehouse (dbt, Airflow)
- Team already maintains CDC infrastructure

---



1. Create a new adapter file (`databases/new_db.py`)
2. Implement the `DatabaseAdapter` interface
3. Update the factory (`databases/__init__.py`)
4. Update `config.yaml` with database-specific params
5. Add dependencies to `requirements.txt`

See [ARCHITECTURE.md](ARCHITECTURE.md#adding-a-new-database-type) for detailed example.

---

## Files

| File | Purpose |
|------|---------|
| `monitor.py` | Main entry point; orchestrates snapshots and diffs |
| `config.yaml` | Table definitions and database configuration |
| `databases/` | Database adapter implementations (extensible) |
| `core/` | Database-agnostic changepoint logic |
| `comparator.py` | Pure change-detection algorithm |
| `ARCHITECTURE.md` | Detailed design and implementation guide |
| `.env.example` | Template for credentials (copy to `.env`) |
| `.gitignore` | Excludes `.env` and `logs/` |

---

## Support & Contributing

For issues or new database adapters, consult [ARCHITECTURE.md](ARCHITECTURE.md) for implementation patterns and testing guidance.
