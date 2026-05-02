import json
from datetime import date

from db import execute_query, execute_many


def _pk_json(row: dict, pk_columns: list[str]) -> str:
    return json.dumps(
        {k: str(row[k.upper()]) for k in pk_columns},
        sort_keys=True,
    )


def _values_json(row: dict, value_columns: list[str]) -> str:
    return json.dumps(
        {k: str(row[k.upper()]) for k in value_columns},
        sort_keys=True,
    )


def take_snapshot(conn, table_cfg: dict, snapshot_date: date) -> list[dict]:
    table = table_cfg["name"]
    cols = table_cfg["pk_columns"] + table_cfg["value_columns"]
    col_list = ", ".join(cols)
    sql = f"SELECT {col_list} FROM {table}"
    return execute_query(conn, sql)


def write_snapshot(
    conn,
    monitoring_cfg: dict,
    table_name: str,
    snapshot_date: date,
    rows: list[dict],
    pk_columns: list[str],
    value_columns: list[str],
) -> None:
    snapshot_table = monitoring_cfg["snapshot_table"]
    sql = f"""
        INSERT INTO {snapshot_table} (snapshot_date, table_name, pk_json, values_json)
        VALUES (%s, %s, PARSE_JSON(%s), PARSE_JSON(%s))
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
    execute_many(conn, sql, data)


def read_snapshot(
    conn,
    monitoring_cfg: dict,
    table_name: str,
    snapshot_date: date,
) -> dict[str, dict]:
    snapshot_table = monitoring_cfg["snapshot_table"]
    sql = f"""
        SELECT
            TO_JSON(pk_json)     AS pk_json,
            TO_JSON(values_json) AS values_json
        FROM {snapshot_table}
        WHERE snapshot_date = %s
          AND table_name    = %s
    """
    rows = execute_query(conn, sql, (snapshot_date.isoformat(), table_name))
    result = {}
    for row in rows:
        pk_str = row["PK_JSON"]
        values = json.loads(row["VALUES_JSON"])
        result[pk_str] = values
    return result


def snapshot_exists(
    conn,
    monitoring_cfg: dict,
    table_name: str,
    snapshot_date: date,
) -> bool:
    snapshot_table = monitoring_cfg["snapshot_table"]
    sql = f"""
        SELECT COUNT(*) AS cnt
        FROM {snapshot_table}
        WHERE snapshot_date = %s
          AND table_name    = %s
    """
    rows = execute_query(conn, sql, (snapshot_date.isoformat(), table_name))
    return rows[0]["CNT"] > 0
