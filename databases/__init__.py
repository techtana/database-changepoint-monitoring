"""Database adapter factory."""
from .base import DatabaseAdapter


def get_adapter(db_type: str, config: dict) -> DatabaseAdapter:
    """
    Factory function to get the appropriate database adapter.

    Args:
        db_type: "snowflake", "bigquery", or "sqlite"
        config: database-specific configuration dict

    Returns:
        Initialized DatabaseAdapter instance
    """
    if db_type == "snowflake":
        from .snowflake import SnowflakeAdapter
        return SnowflakeAdapter(config)
    elif db_type == "bigquery":
        from .bigquery import BigQueryAdapter
        return BigQueryAdapter(config)
    elif db_type == "sqlite":
        from .sqlite import SQLiteAdapter
        return SQLiteAdapter(config)
    else:
        raise ValueError(
            f"Unknown database type: {db_type}. "
            f"Supported: snowflake, bigquery, sqlite"
        )


__all__ = ["get_adapter", "DatabaseAdapter"]
