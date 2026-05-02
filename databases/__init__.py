"""Database adapter factory."""
from .base import DatabaseAdapter
from .snowflake import SnowflakeAdapter
from .bigquery import BigQueryAdapter
from .sqlite import SQLiteAdapter


def get_adapter(db_type: str, config: dict) -> DatabaseAdapter:
    """
    Factory function to get the appropriate database adapter.

    Args:
        db_type: "snowflake", "bigquery", or "sqlite"
        config: database-specific configuration dict

    Returns:
        Initialized DatabaseAdapter instance
    """
    adapters = {
        "snowflake": SnowflakeAdapter,
        "bigquery": BigQueryAdapter,
        "sqlite": SQLiteAdapter,
    }

    adapter_class = adapters.get(db_type)
    if not adapter_class:
        raise ValueError(
            f"Unknown database type: {db_type}. "
            f"Supported: {', '.join(adapters.keys())}"
        )

    return adapter_class(config)


__all__ = ["get_adapter", "DatabaseAdapter"]
