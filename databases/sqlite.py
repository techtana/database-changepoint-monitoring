"""SQLite database adapter."""
import os
import sqlite3

from .base import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):
    """Adapter for SQLite databases (file or in-memory)."""

    def __init__(self, config: dict):
        """
        Initialize adapter with SQLite configuration.

        config should contain:
          path - file path for SQLite DB (":memory:" for in-memory)
        """
        self.config = config
        self.connection = None

    def connect(self):
        """Establish SQLite connection."""
        path = self.config.get("path", ":memory:")
        self.connection = sqlite3.connect(path)
        # Enable full column names in result dicts
        self.connection.row_factory = sqlite3.Row
        return self

    def close(self) -> None:
        """Close SQLite connection."""
        if self.connection:
            self.connection.close()

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT query and return rows as dicts."""
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        # Convert sqlite3.Row objects to dicts
        rows = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        return rows

    def execute_many(self, sql: str, rows: list[tuple]) -> None:
        """Bulk insert multiple rows."""
        if not rows:
            return
        cursor = self.connection.cursor()
        cursor.executemany(sql, rows)
        self.connection.commit()
        cursor.close()

    def get_support_tables_ddl(
        self, snapshot_table: str, changelog_table: str
    ) -> tuple[str, str]:
        """Return SQLite DDL for snapshot and changelog tables."""
        snapshot_ddl = f"""
            CREATE TABLE IF NOT EXISTS {snapshot_table} (
                snapshot_date   DATE         NOT NULL,
                table_name      TEXT         NOT NULL,
                pk_json         TEXT         NOT NULL,
                values_json     TEXT         NOT NULL
            )
        """
        changelog_ddl = f"""
            CREATE TABLE IF NOT EXISTS {changelog_table} (
                change_date     DATE         NOT NULL,
                table_name      TEXT         NOT NULL,
                pk_json         TEXT         NOT NULL,
                change_type     TEXT         NOT NULL,
                column_name     TEXT,
                old_value       TEXT,
                new_value       TEXT
            )
        """
        return snapshot_ddl, changelog_ddl

    def parse_json_column(self, col_name: str) -> str:
        """SQLite stores JSON as TEXT, no parsing function needed."""
        return col_name

    def json_constructor(self, value_expr: str) -> str:
        """SQLite stores JSON as plain TEXT."""
        return value_expr
