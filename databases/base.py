"""Abstract base class for database adapters."""
from abc import ABC, abstractmethod
from typing import Any


class DatabaseAdapter(ABC):
    """Base adapter for different database backends."""

    @abstractmethod
    def connect(self):
        """Establish database connection. Returns self for chaining."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT query and return rows as dicts."""
        pass

    @abstractmethod
    def execute_many(self, sql: str, rows: list[tuple]) -> None:
        """Bulk insert multiple rows."""
        pass

    @abstractmethod
    def get_support_tables_ddl(
        self, snapshot_table: str, changelog_table: str
    ) -> tuple[str, str]:
        """
        Return DDL for snapshot and changelog tables.

        Returns:
            (snapshot_ddl, changelog_ddl)
        """
        pass

    def quote_identifier(self, name: str) -> str:
        """Quote an identifier (table/column name) for this DB dialect."""
        return name

    def parse_json_column(self, col_name: str) -> str:
        """
        Return SQL expression to parse a JSON column.
        Used in INSERT statements to convert string to native JSON type.
        """
        return col_name

    def json_constructor(self, value_expr: str) -> str:
        """
        Return SQL to construct a JSON value from an expression.
        For INSERT statements that need to store JSON strings.
        """
        return value_expr
