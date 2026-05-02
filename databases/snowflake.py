"""Snowflake database adapter."""
import os
import snowflake.connector

from .base import DatabaseAdapter


class SnowflakeAdapter(DatabaseAdapter):
    """Adapter for Snowflake databases."""

    def __init__(self, config: dict):
        """
        Initialize adapter with Snowflake configuration.

        config should contain:
          account, user, password, warehouse, database, role
        May use ${ENV_VAR} syntax for env var substitution.
        """
        self.config = self._substitute_env_vars(config)
        self.connection = None

    def _substitute_env_vars(self, config: dict) -> dict:
        """Replace ${VAR_NAME} with environment variable values."""
        result = {}
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                result[key] = os.environ.get(var_name)
                if result[key] is None:
                    raise EnvironmentError(f"Environment variable not set: {var_name}")
            else:
                result[key] = value
        return result

    def connect(self):
        """Establish Snowflake connection."""
        required = ["account", "user", "password", "warehouse", "database", "role"]
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            raise EnvironmentError(f"Missing Snowflake config: {', '.join(missing)}")

        self.connection = snowflake.connector.connect(
            account=self.config["account"],
            user=self.config["user"],
            password=self.config["password"],
            warehouse=self.config["warehouse"],
            database=self.config["database"],
            role=self.config["role"],
        )
        return self

    def close(self) -> None:
        """Close Snowflake connection."""
        if self.connection:
            self.connection.close()

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT query and return rows as dicts."""
        with self.connection.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0].upper() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def execute_many(self, sql: str, rows: list[tuple]) -> None:
        """Bulk insert multiple rows."""
        if not rows:
            return
        with self.connection.cursor() as cur:
            cur.executemany(sql, rows)
        self.connection.commit()

    def get_support_tables_ddl(
        self, snapshot_table: str, changelog_table: str
    ) -> tuple[str, str]:
        """Return Snowflake DDL for snapshot and changelog tables."""
        snapshot_ddl = f"""
            CREATE TABLE IF NOT EXISTS {snapshot_table} (
                snapshot_date   DATE         NOT NULL,
                table_name      VARCHAR(255) NOT NULL,
                pk_json         VARIANT      NOT NULL,
                values_json     VARIANT      NOT NULL
            )
        """
        changelog_ddl = f"""
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
        return snapshot_ddl, changelog_ddl

    def parse_json_column(self, col_name: str) -> str:
        """Snowflake VARIANT columns need PARSE_JSON to convert strings."""
        return f"PARSE_JSON({col_name})"

    def json_constructor(self, value_expr: str) -> str:
        """Snowflake uses PARSE_JSON for JSON string conversion."""
        return f"PARSE_JSON({value_expr})"
