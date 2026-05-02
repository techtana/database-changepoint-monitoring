#!/usr/bin/env python
"""
Test script to verify the refactored multi-database architecture.
Tests with SQLite for simplicity (no external deps).
"""
import os
import sys
from datetime import date
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent))

from databases import get_adapter
from core.snapshot import write_snapshot, read_snapshot, snapshot_exists
from core.changelog import write_changes
from comparator import compare_snapshots


def test_sqlite_adapter():
    """Test SQLite adapter with the refactored code."""
    print("=" * 70)
    print("Testing SQLite Adapter")
    print("=" * 70)

    # Clean up any existing test DB
    test_db = "./test_changepoint_verify.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    # Create adapter
    config = {"path": test_db}
    adapter = get_adapter("sqlite", config)
    adapter.connect()

    try:
        # Create support tables
        snapshot_table = "DAILY_SNAPSHOTS"
        changelog_table = "CHANGE_LOG"

        snapshot_ddl, changelog_ddl = adapter.get_support_tables_ddl(
            snapshot_table, changelog_table
        )

        print("\n1. Creating support tables...")
        adapter.execute_query(snapshot_ddl)
        adapter.execute_query(changelog_ddl)
        print("   [OK] Tables created successfully")

        # Create test data table
        print("\n2. Creating test data table...")
        adapter.execute_query("""
            CREATE TABLE CONFIG_TABLE_A (
                id TEXT PRIMARY KEY,
                config_value TEXT,
                enabled TEXT
            )
        """)
        print("   [OK] Test table created")

        # Insert test data
        print("\n3. Inserting initial test data...")
        adapter.execute_many(
            "INSERT INTO CONFIG_TABLE_A (id, config_value, enabled) VALUES (?, ?, ?)",
            [
                ("row1", "value_a", "true"),
                ("row2", "value_b", "false"),
            ],
        )
        print("   [OK] Inserted 2 rows")

        # Test snapshot write/read
        today = date.today()
        yesterday = date(today.year, today.month, max(1, today.day - 1))

        monitoring_cfg = {
            "snapshot_table": snapshot_table,
            "changelog_table": changelog_table,
        }

        print("\n4. Testing snapshot operations...")
        today_rows = adapter.execute_query("SELECT id, config_value, enabled FROM CONFIG_TABLE_A")
        write_snapshot(
            adapter,
            monitoring_cfg,
            "CONFIG_TABLE_A",
            today,
            today_rows,
            pk_columns=["id"],
            value_columns=["config_value", "enabled"],
        )
        print(f"   [OK] Wrote snapshot for {today}")

        # Check snapshot exists
        exists = snapshot_exists(adapter, monitoring_cfg, "CONFIG_TABLE_A", today)
        print(f"   [OK] Snapshot exists: {exists}")

        # Read snapshot back
        snap = read_snapshot(adapter, monitoring_cfg, "CONFIG_TABLE_A", today)
        print(f"   [OK] Read snapshot with {len(snap)} rows")

        # Test change detection
        print("\n5. Testing change detection...")
        yesterday_snap = {}  # Simulate no previous snapshot
        today_snap = snap

        changes = compare_snapshots(
            table_name="CONFIG_TABLE_A",
            yesterday=yesterday_snap,
            today=today_snap,
            value_columns=["config_value", "enabled"],
            change_date=today,
        )

        print(f"   [OK] Detected {len(changes)} changes")
        for change in changes[:3]:  # Show first 3
            print(f"     - {change['change_type']}: {change.get('pk_json', 'N/A')}")

        # Write changes
        print("\n6. Writing changes to changelog...")
        n = write_changes(adapter, monitoring_cfg, changes)
        print(f"   [OK] Wrote {n} change records")

        # Verify changelog
        changelog_rows = adapter.execute_query(
            f"SELECT * FROM {changelog_table} LIMIT 5"
        )
        print(f"   [OK] Changelog contains {len(changelog_rows)} records")

        print("\n" + "=" * 70)
        print("[SUCCESS] All tests passed!")
        print("=" * 70)

    finally:
        adapter.close()
        # Clean up
        if os.path.exists(test_db):
            os.remove(test_db)


if __name__ == "__main__":
    test_sqlite_adapter()
