import os
import snowflake.connector


def get_connection() -> snowflake.connector.SnowflakeConnection:
    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_ROLE",
    ]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        role=os.environ["SNOWFLAKE_ROLE"],
    )


def execute_query(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0].upper() for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def execute_many(conn, sql: str, rows: list[tuple]) -> None:
    if not rows:
        return
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()


def ensure_support_tables(conn, cfg: dict) -> None:
    snapshot_table = cfg["monitoring"]["snapshot_table"]
    changelog_table = cfg["monitoring"]["changelog_table"]

    ddl_snapshot = f"""
        CREATE TABLE IF NOT EXISTS {snapshot_table} (
            snapshot_date   DATE         NOT NULL,
            table_name      VARCHAR(255) NOT NULL,
            pk_json         VARIANT      NOT NULL,
            values_json     VARIANT      NOT NULL
        )
    """
    ddl_changelog = f"""
        CREATE TABLE IF NOT EXISTS {changelog_table} (
            change_date   DATE         NOT NULL,
            table_name    VARCHAR(255) NOT NULL,
            pk_json       VARIANT      NOT NULL,
            change_type   VARCHAR(10)  NOT NULL,
            column_name   VARCHAR(255),
            old_value     VARCHAR(65535),
            new_value     VARCHAR(65535)
        )
    """
    with conn.cursor() as cur:
        cur.execute(ddl_snapshot)
        cur.execute(ddl_changelog)
    conn.commit()
