"""Snapshot operations using database adapter."""
import json
from datetime import date

from databases.base import DatabaseAdapter


def take_snapshot(adapter: DatabaseAdapter, table_cfg: dict, snapshot_date: date) -> list[dict]:
    """Read a table snapshot."""
    table = table_cfg["name"]
    cols = table_cfg["pk_columns"] + table_cfg["value_columns"]
    col_list = ", ".join(cols)
    sql = f"SELECT {col_list} FROM {table}"
    return adapter.execute_query(sql)


def _normalize_row_keys(row: dict) -> dict:
    """Normalize row keys to uppercase for consistent access."""
    return {k.upper(): v for k, v in row.items()}


def _pk_json(row: dict, pk_columns: list[str]) -> str:
    """Serialize PK columns to sorted JSON."""
    normalized = _normalize_row_keys(row)
    return json.dumps(
        {k: str(normalized[k.upper()]) for k in pk_columns},
        sort_keys=True,
    )


def _values_json(row: dict, value_columns: list[str]) -> str:
    """Serialize value columns to sorted JSON."""
    normalized = _normalize_row_keys(row)
    return json.dumps(
        {k: str(normalized[k.upper()]) for k in value_columns},
        sort_keys=True,
    )


def write_snapshot(
    adapter: DatabaseAdapter,
    monitoring_cfg: dict,
    table_name: str,
    snapshot_date: date,
    rows: list[dict],
    pk_columns: list[str],
    value_columns: list[str],
) -> None:
    """Write a snapshot to the database."""
    snapshot_table = monitoring_cfg["snapshot_table"]

    # Build SQL with adapter-specific JSON constructor
    parsed_pk = adapter.parse_json_column("?")
    parsed_values = adapter.parse_json_column("?")

    sql = f"""
        INSERT INTO {snapshot_table} (snapshot_date, table_name, pk_json, values_json)
        VALUES (?, ?, {parsed_pk}, {parsed_values})
    """

    data = [
        (
            snapshot_date.isoformat(),
            table_name,
            _pk_json(row, pk_columns),
            _values_json(row, value_columns),
        )
        for row in rows
    ]
    adapter.execute_many(sql, data)


def read_snapshot(
    adapter: DatabaseAdapter,
    monitoring_cfg: dict,
    table_name: str,
    snapshot_date: date,
) -> dict[str, dict]:
    """Read a snapshot from the database."""
    snapshot_table = monitoring_cfg["snapshot_table"]
    sql = f"""
        SELECT
            pk_json,
            values_json
        FROM {snapshot_table}
        WHERE snapshot_date = ?
          AND table_name    = ?
    """
    rows = adapter.execute_query(sql, (snapshot_date.isoformat(), table_name))
    result = {}
    for row in rows:
        normalized = _normalize_row_keys(row)
        pk_str = normalized["PK_JSON"]
        values = json.loads(normalized["VALUES_JSON"])
        result[pk_str] = values
    return result


def snapshot_exists(
    adapter: DatabaseAdapter,
    monitoring_cfg: dict,
    table_name: str,
    snapshot_date: date,
) -> bool:
    """Check if a snapshot exists for the given date and table."""
    snapshot_table = monitoring_cfg["snapshot_table"]
    sql = f"""
        SELECT COUNT(*) AS cnt
        FROM {snapshot_table}
        WHERE snapshot_date = ?
          AND table_name    = ?
    """
    rows = adapter.execute_query(sql, (snapshot_date.isoformat(), table_name))
    normalized = _normalize_row_keys(rows[0])
    return normalized["CNT"] > 0
