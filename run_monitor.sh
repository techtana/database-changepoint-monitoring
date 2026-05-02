#!/usr/bin/env bash
# -----------------------------------------------------------------------
#  Snowflake Daily Change Monitor — Unix/macOS launcher
#
#  Usage:
#    chmod +x run_monitor.sh
#    ./run_monitor.sh
#
#  To schedule with cron (e.g. daily at 06:00):
#    crontab -e
#    0 6 * * * /path/to/database_changepoint_monitoring/run_monitor.sh
#
#  Credentials are read from environment variables. Set them in your
#  shell profile (~/.bashrc, ~/.zshrc) or in a .env file in this directory.
# -----------------------------------------------------------------------

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"
python monitor.py >> "$LOG_DIR/monitor.log" 2>&1
