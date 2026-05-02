"""Changelog operations using database adapter."""
from databases.base import DatabaseAdapter


def write_changes(adapter: DatabaseAdapter, monitoring_cfg: dict, changes: list[dict]) -> int:
    """Write detected changes to the changelog table."""
    if not changes:
        return 0

    changelog_table = monitoring_cfg["changelog_table"]
    parsed_pk = adapter.parse_json_column("?")

    sql = f"""
        INSERT INTO {changelog_table}
            (change_date, table_name, pk_json, change_type, column_name, old_value, new_value)
        VALUES (?, ?, {parsed_pk}, ?, ?, ?, ?)
    """

    rows = [
        (
            c["change_date"],
            c["table_name"],
            c["pk_json"],
            c["change_type"],
            c["column_name"],
            c["old_value"],
            c["new_value"],
        )
        for c in changes
    ]
    adapter.execute_many(sql, rows)
    return len(rows)
