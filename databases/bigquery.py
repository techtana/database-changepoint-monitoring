"""BigQuery database adapter."""
import os
from google.cloud import bigquery
from google.oauth2 import service_account

from .base import DatabaseAdapter


class BigQueryAdapter(DatabaseAdapter):
    """Adapter for Google BigQuery databases."""

    def __init__(self, config: dict):
        """
        Initialize adapter with BigQuery configuration.

        config should contain:
          project, dataset
        Optional: credentials_path (path to service account JSON)
        May use ${ENV_VAR} syntax for env var substitution.
        """
        self.config = self._substitute_env_vars(config)
        self.client = None
        self.project = self.config.get("project")
        self.dataset = self.config.get("dataset")

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
        """Establish BigQuery connection."""
        if not self.project or not self.dataset:
            raise EnvironmentError("Missing BigQuery config: project, dataset")

        credentials_path = self.config.get("credentials_path")
        if credentials_path:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            self.client = bigquery.Client(
                project=self.project, credentials=credentials
            )
        else:
            self.client = bigquery.Client(project=self.project)
        return self

    def close(self) -> None:
        """Close BigQuery connection (no-op, but keep for interface compatibility)."""
        pass

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT query and return rows as dicts."""
        # BigQuery uses @param1, @param2 for parameters
        # For simplicity, we use format strings (safe for internal use only)
        if params:
            # Simple substitution for positional params
            sql_formatted = sql
            for i, param in enumerate(params):
                sql_formatted = sql_formatted.replace("%s", f"'{param}'", 1)
            sql = sql_formatted

        query_job = self.client.query(sql)
        rows = query_job.result()
        return [dict(row.items()) for row in rows]

    def execute_many(self, sql: str, rows: list[tuple]) -> None:
        """Bulk insert multiple rows using insert_rows_json."""
        if not rows:
            return

        # Parse table name from INSERT statement
        # Expected format: INSERT INTO table_name (cols) VALUES (...)
        parts = sql.split()
        table_idx = parts.index("INTO") + 1
        table_name = parts[table_idx]

        # Get column names from INSERT statement
        cols_start = sql.index("(")
        cols_end = sql.index(")")
        cols_str = sql[cols_start + 1 : cols_end]
        columns = [c.strip() for c in cols_str.split(",")]

        # Convert tuples to dicts
        json_rows = []
        for row in rows:
            json_row = dict(zip(columns, row))
            json_rows.append(json_row)

        # Get fully qualified table name
        table_ref = f"{self.project}.{self.dataset}.{table_name}"
        table = self.client.get_table(table_ref)

        errors = self.client.insert_rows_json(table, json_rows)
        if errors:
            raise Exception(f"BigQuery insert errors: {errors}")

    def get_support_tables_ddl(
        self, snapshot_table: str, changelog_table: str
    ) -> tuple[str, str]:
        """Return BigQuery DDL for snapshot and changelog tables."""
        # BigQuery uses different naming and data types
        snapshot_ddl = f"""
            CREATE TABLE IF NOT EXISTS {self.project}.{self.dataset}.{snapshot_table} (
                snapshot_date   DATE         NOT NULL,
                table_name      STRING       NOT NULL,
                pk_json         STRING       NOT NULL,
                values_json     STRING       NOT NULL
            )
        """
        changelog_ddl = f"""
            CREATE TABLE IF NOT EXISTS {self.project}.{self.dataset}.{changelog_table} (
                change_date     DATE         NOT NULL,
                table_name      STRING       NOT NULL,
                pk_json         STRING       NOT NULL,
                change_type     STRING       NOT NULL,
                column_name     STRING,
                old_value       STRING,
                new_value       STRING
            )
        """
        return snapshot_ddl, changelog_ddl

    def parse_json_column(self, col_name: str) -> str:
        """BigQuery JSON columns are already strings, no parsing needed."""
        return col_name

    def json_constructor(self, value_expr: str) -> str:
        """BigQuery stores JSON as STRING, no conversion needed."""
        return value_expr
