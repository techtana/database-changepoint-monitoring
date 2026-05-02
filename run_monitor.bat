@echo off
REM -----------------------------------------------------------------------
REM  Snowflake Daily Change Monitor — Windows Task Scheduler launcher
REM
REM  Prerequisites:
REM    1. Set the following as SYSTEM environment variables
REM       (Control Panel > System > Advanced > Environment Variables):
REM         SNOWFLAKE_ACCOUNT    e.g. myorg-myaccount
REM         SNOWFLAKE_USER       your Snowflake username
REM         SNOWFLAKE_PASSWORD   your Snowflake password
REM         SNOWFLAKE_WAREHOUSE  e.g. COMPUTE_WH
REM         SNOWFLAKE_DATABASE   e.g. MYDB
REM         SNOWFLAKE_ROLE       e.g. SYSADMIN
REM    2. Install Python dependencies once:
REM         pip install -r requirements.txt
REM
REM  To schedule: open Task Scheduler, create a Daily task that runs
REM  this .bat file. Set "Start in" to the project directory.
REM -----------------------------------------------------------------------

REM Resolve the project directory from the location of this script — no hardcoded paths.
SET PROJECT_DIR=%~dp0

cd /d "%PROJECT_DIR%"
python monitor.py >> "%PROJECT_DIR%logs\monitor.log" 2>&1
