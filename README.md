# Snowflake Configuration Change Monitor

A lightweight Python tool that takes a daily snapshot of Snowflake configuration tables and records exactly what changed — new rows, deleted rows, and updated values — into a queryable change-log table.

---

## Background

Several software systems read their runtime configuration from Snowflake tables. These configs are edited manually by humans and changes can be hard to trace after the fact. The monitor provides a historical audit trail: given any date, you can query which config rows were added, removed, or had specific values changed.

A key characteristic of the config tables is that primary key values are not always standard identifiers. Some rows use regex-pattern PKs (e.g. `regex(abc.*)`) that the consuming software resolves at runtime by matching the pattern against an actual lookup key. The monitor treats all PK values as opaque strings — no regex resolution is performed at monitoring time — which is the correct approach for tracking row identity across snapshots.

---

## Design

### Approach: daily snapshot diff

Rather than using database triggers or CDC (Change Data Capture), the tool takes a full snapshot of each monitored table once per day and compares it against the previous day's snapshot. This approach was chosen because:

- It works without schema changes or trigger permissions on the source tables.
- It is resilient to tables that have no `updated_at` timestamp.
- The full snapshot is stored, making it easy to reconstruct the complete config state for any past date.

### Data flow

```
Source config tables
        │
        ▼
  take_snapshot()          SELECT pk_cols + value_cols
        │
        ▼
  write_snapshot()         Persist to DAILY_SNAPSHOTS (Snowflake VARIANT columns)
        │
        ▼
  compare_snapshots()      Pure set-arithmetic diff — no DB I/O
        │
        ▼
  write_changes()          Bulk-insert into CHANGE_LOG
```

### Snowflake support tables

**`DAILY_SNAPSHOTS`** — one row per source-table row per day. PK and value columns are serialised as JSON `VARIANT`, making the schema agnostic to the structure of any individual config table.

| Column | Type | Notes |
|---|---|---|
| `snapshot_date` | DATE | The day of the snapshot |
| `table_name` | VARCHAR | Fully-qualified source table name |
| `pk_json` | VARIANT | JSON object of PK column → value |
| `values_json` | VARIANT | JSON object of monitored value column → value |

**`CHANGE_LOG`** — one row per changed field per day.

| Column | Type | Notes |
|---|---|---|
| `change_date` | DATE | Day the change was detected |
| `table_name` | VARCHAR | Source table |
| `pk_json` | VARIANT | Row identity |
| `change_type` | VARCHAR | `INSERT`, `DELETE`, or `UPDATE` |
| `column_name` | VARCHAR | NULL for INSERT/DELETE; column name for UPDATE |
| `old_value` | VARCHAR | Previous value (NULL for INSERT) |
| `new_value` | VARCHAR | New value (NULL for DELETE) |

For `INSERT` and `DELETE` events, `old_value` / `new_value` holds the full JSON-serialised values dict so no information is lost.

### Module structure

| File | Role |
|---|---|
| `db.py` | Snowflake connection, query helpers, DDL bootstrap |
| `snapshot.py` | Read/write snapshots; idempotency check |
| `comparator.py` | Pure diff function — no DB I/O, fully unit-testable |
| `changelog.py` | Bulk-insert change rows |
| `monitor.py` | Orchestrator entry point |
| `config.yaml` | Table definitions (edit this for your environment) |
| `run_monitor.bat` | Windows Task Scheduler launcher (self-locating, no hardcoded paths) |
| `run_monitor.sh` | Unix/macOS cron launcher |
| `.env.example` | Template for Snowflake credentials — copy to `.env` |
| `.gitignore` | Excludes `.env` and `logs/` from version control |

---

## Key Decisions

**1. Schema-agnostic snapshot storage via JSON**
Different config tables have different column sets (some wide, some long, varying PK arities). Storing `pk_json` and `values_json` as Snowflake `VARIANT` means a single pair of support tables serves all monitored tables without per-table schema changes.

**2. PK values treated as opaque strings**
Regex-pattern PKs like `regex(abc.*)` are stored and compared as literal strings. Row identity across two snapshots is determined by exact string equality of the serialised PK JSON. This is correct: if a human changes a PK from `regex(abc.*)` to `regex(abc_\d+.*)`, that is a genuine row replacement (DELETE + INSERT), not an update to a value column.

**3. Sorted JSON keys for stable identity**
All `pk_json` values are produced with `json.dumps(..., sort_keys=True)`. This ensures that a row with `{pk1: "A", pk2: "B"}` always hashes to the same string regardless of the order columns were returned by Snowflake.

**4. All values cast to `str` before comparison**
Snowflake may return numeric, boolean, or NULL values. Casting everything to `str` at snapshot time avoids type-change false-positives (e.g. integer `1` vs string `"1"` being flagged as an update when the column type is altered). The cast policy is applied consistently at both write time and compare time.

**5. Idempotent daily runs**
Before taking a snapshot, the script checks whether one already exists for today. If the script is re-run (e.g. after a failure mid-way), it skips already-completed tables rather than creating duplicate snapshot or change-log rows.

**6. First-run / gap handling**
If no snapshot exists for "yesterday" (first ever run, or a day was skipped), all current rows are recorded as `INSERT` events in the change log. This seeds the audit trail without producing false DELETE events for rows that were simply never captured before.

---

## Configuration

Edit `config.yaml` to point at your real Snowflake tables:

```yaml
monitoring:
  snapshot_table: "MYDB.MONITORING.DAILY_SNAPSHOTS"
  changelog_table: "MYDB.MONITORING.CHANGE_LOG"

tables:
  - name: "MYDB.CONFIG.TABLE_A"
    pk_columns:    [pk1, pk2, pk3]
    value_columns: [val1, val2, val3]
```

- `pk_columns` — columns that uniquely identify a row. Values may be literal strings or regex patterns; both work without any special treatment.
- `value_columns` — the only columns whose values are compared for change detection. Group/metadata columns not listed here are ignored.

---

## Setup

**1. Clone / copy the project to any directory on your machine.**
No paths are hardcoded anywhere in the project; launchers resolve their own location at runtime.

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure credentials**

Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env   # Unix/macOS
copy .env.example .env  # Windows
```

`.env` is loaded automatically by `monitor.py` via `python-dotenv` and is excluded from version control by `.gitignore`. Alternatively, set the same keys as system or shell environment variables (required for Task Scheduler / cron running under a service account).

**4. Configure tables**

Edit `config.yaml` — replace the `MYDB.*` placeholders with your real Snowflake fully-qualified table names, and set the correct `pk_columns` and `value_columns` for each table.

**5. Run manually the first time**
```bash
python monitor.py
```
This creates the support tables if they do not exist, takes the first snapshot, and populates the change log with INSERT baseline rows.

**6. Schedule**

_Windows — Task Scheduler:_
- Create a Daily task pointing at `run_monitor.bat`.
- Set "Start in" to the project directory (or leave blank — the script self-locates via `%~dp0`).
- Enable "Run whether user is logged on or not" and "Run with highest privileges".
- Set `SNOWFLAKE_*` vars as System environment variables so the service account can read them.
- Output is appended to `logs\monitor.log`.

_Unix / macOS — cron:_
```bash
chmod +x run_monitor.sh
crontab -e
# Add: run daily at 06:00
0 6 * * * /path/to/database_changepoint_monitoring/run_monitor.sh
```
Output is appended to `logs/monitor.log`.

---

## Querying the Change Log

**All changes on a given day:**
```sql
SELECT * FROM MYDB.MONITORING.CHANGE_LOG
WHERE change_date = '2026-05-02'
ORDER BY table_name, pk_json, column_name;
```

**History of a specific config row:**
```sql
SELECT * FROM MYDB.MONITORING.CHANGE_LOG
WHERE table_name = 'MYDB.CONFIG.TABLE_A'
  AND pk_json:pk1::STRING = 'regex(abc.*)'
ORDER BY change_date;
```

**What the config looked like on a specific date:**
```sql
SELECT TO_JSON(pk_json), TO_JSON(values_json)
FROM MYDB.MONITORING.DAILY_SNAPSHOTS
WHERE table_name    = 'MYDB.CONFIG.TABLE_A'
  AND snapshot_date = '2026-05-01';
```

---

## Limitations

- **Daily granularity only.** Multiple changes to the same row within a single day are not captured; only the state at snapshot time is recorded. If a value is changed and then reverted within the same day, no change will be detected.

- **No intra-day alerting.** The tool is designed for end-of-day auditing, not real-time monitoring. For immediate alerts on config changes, database triggers or Snowflake Dynamic Tables would be more appropriate.

- **Snapshot storage grows linearly.** `DAILY_SNAPSHOTS` accumulates one row per source row per day indefinitely. For large config tables or long retention periods, a periodic purge policy should be added (e.g. `DELETE FROM ... WHERE snapshot_date < DATEADD(day, -90, CURRENT_DATE)`).

- **Regex PKs are not resolved.** The monitor does not interpret `regex(abc.*)` patterns or determine which actual runtime lookup keys they match. It only tracks whether the pattern string itself changed. If the consuming software's regex matching logic is what you want to audit, that is out of scope.

- **Schema changes break snapshots.** If a `pk_column` or `value_column` listed in `config.yaml` is renamed or dropped in the source table, the `take_snapshot` SELECT will fail. The config must be updated in sync with any source schema changes.

- **No multi-day gap recovery.** If the scheduler is offline for several days, only the most recent missed day is effectively captured on the next run (today vs yesterday). Rows that changed and reverted during the gap will not appear in the log.

- **Credentials are plain-text environment variables.** For production use, consider replacing `SNOWFLAKE_PASSWORD` with key-pair authentication or a secrets manager integration.
