from db import execute_many


def write_changes(conn, monitoring_cfg: dict, changes: list[dict]) -> int:
    if not changes:
        return 0
    changelog_table = monitoring_cfg["changelog_table"]
    sql = f"""
        INSERT INTO {changelog_table}
            (change_date, table_name, pk_json, change_type, column_name, old_value, new_value)
        VALUES (%s, %s, PARSE_JSON(%s), %s, %s, %s, %s)
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
    execute_many(conn, sql, rows)
    return len(rows)
