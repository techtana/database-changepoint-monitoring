import logging
import os
import sys
from datetime import date, timedelta

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from databases import get_adapter
from core.changelog import write_changes
from core.snapshot import read_snapshot, snapshot_exists, take_snapshot, write_snapshot
from comparator import compare_snapshots


def _setup_logging() -> None:
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _substitute_env_vars(obj):
    """Recursively substitute ${VAR_NAME} with environment variables."""
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var_name = obj[2:-1]
        value = os.environ.get(var_name)
        if value is None:
            raise EnvironmentError(f"Environment variable not set: {var_name}")
        return value
    return obj


def run(config_path: str = "config.yaml") -> None:
    _setup_logging()
    log = logging.getLogger(__name__)

    cfg = load_config(config_path)
    cfg = _substitute_env_vars(cfg)

    database_cfg = cfg.get("database", {})
    db_type = database_cfg.get("type", "snowflake")
    db_config = database_cfg.get(db_type, {})

    monitoring_cfg = cfg["monitoring"]

    # Get adapter and establish connection
    adapter = get_adapter(db_type, db_config)
    adapter.connect()

    try:
        # Create support tables if needed
        snapshot_table = monitoring_cfg["snapshot_table"]
        changelog_table = monitoring_cfg["changelog_table"]
        snapshot_ddl, changelog_ddl = adapter.get_support_tables_ddl(
            snapshot_table, changelog_table
        )
        adapter.execute_query(snapshot_ddl)
        adapter.execute_query(changelog_ddl)

        today = date.today()
        yesterday = today - timedelta(days=1)

        for table_cfg in cfg["tables"]:
            table_name = table_cfg["name"]
            pk_columns = table_cfg["pk_columns"]
            value_columns = table_cfg["value_columns"]

            if snapshot_exists(adapter, monitoring_cfg, table_name, today):
                log.info("[%s] Snapshot already exists for today — skipping.", table_name)
                continue

            log.info("[%s] Taking snapshot for %s …", table_name, today)
            today_rows = take_snapshot(adapter, table_cfg, today)
            write_snapshot(
                adapter, monitoring_cfg, table_name, today, today_rows, pk_columns, value_columns
            )
            log.info("[%s] Wrote %d rows to snapshot.", table_name, len(today_rows))

            yesterday_snap = read_snapshot(adapter, monitoring_cfg, table_name, yesterday)
            if not yesterday_snap:
                log.warning(
                    "[%s] No snapshot found for %s (first run or gap). "
                    "Recording all current rows as INSERT baseline.",
                    table_name, yesterday,
                )

            today_snap = read_snapshot(adapter, monitoring_cfg, table_name, today)

            changes = compare_snapshots(
                table_name=table_name,
                yesterday=yesterday_snap,
                today=today_snap,
                value_columns=value_columns,
                change_date=today,
            )

            n = write_changes(adapter, monitoring_cfg, changes)

            inserts  = sum(1 for c in changes if c["change_type"] == "INSERT")
            deletes  = sum(1 for c in changes if c["change_type"] == "DELETE")
            updates  = sum(1 for c in changes if c["change_type"] == "UPDATE")
            log.info(
                "[%s] Changes written: %d inserts, %d deletes, %d update-columns  (total rows: %d)",
                table_name, inserts, deletes, updates, n,
            )
    finally:
        adapter.close()


if __name__ == "__main__":
    run()
