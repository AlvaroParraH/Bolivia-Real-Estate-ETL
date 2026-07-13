# dbt Snowflake Governance

## Scope
This file defines the minimum-access governance model for dbt in this repository.

## Environment Context (from .env)
- Snowflake account: `JDYVEHY-PZ87907`
- dbt user: `DBT_ADMIN`
- dbt role: `<your_role>`
- dbt warehouse: `<your_warehouse>`
- Target database: `BOLIVIA_REAL_STATE`
- Target schema: `RAW`

Notes:
- Role and warehouse are still placeholders in `.env`; replace them before running dbt.
- Secrets (for example `SNOWFLAKE_PASSWORD`) must never be stored in governance docs.

## Required Privileges
### 1) Warehouse
- `USAGE` on the dbt warehouse
- `OPERATE` only if dbt should resume/suspend warehouse

### 2) Target Database and Schema (write area)
- `USAGE` on target database
- `USAGE` on target schema
- `CREATE TABLE` on target schema
- `CREATE VIEW` on target schema
- `CREATE STAGE` on target schema
- `CREATE FILE FORMAT` on target schema
- Optional: `CREATE SCHEMA` on target database if dbt should auto-create schemas

### 3) Source Data (read area)
- `USAGE` on source database(s)
- `USAGE` on source schema(s)
- `SELECT` on source tables/views

## Quick Setup SQL
Run this in Snowflake. Replace placeholder values before running.

```sql
-- Run with a high-privilege admin role
-- USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS DBT_DEV_ROLE;

-- Optional: grant role to your dbt user
GRANT ROLE DBT_DEV_ROLE TO USER DBT_ADMIN;

-- Switch to object admin role for database/schema creation
-- USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS BOLIVIA_REAL_STATE;
CREATE SCHEMA IF NOT EXISTS BOLIVIA_REAL_STATE.RAW;

-- Warehouse access (replace <your_warehouse>)
GRANT USAGE ON WAREHOUSE <your_warehouse> TO ROLE DBT_DEV_ROLE;

-- dbt write permissions on target area
GRANT USAGE ON DATABASE BOLIVIA_REAL_STATE TO ROLE DBT_DEV_ROLE;
GRANT USAGE ON SCHEMA BOLIVIA_REAL_STATE.RAW TO ROLE DBT_DEV_ROLE;
GRANT CREATE TABLE ON SCHEMA BOLIVIA_REAL_STATE.RAW TO ROLE DBT_DEV_ROLE;
GRANT CREATE VIEW ON SCHEMA BOLIVIA_REAL_STATE.RAW TO ROLE DBT_DEV_ROLE;
GRANT CREATE STAGE ON SCHEMA BOLIVIA_REAL_STATE.RAW TO ROLE DBT_DEV_ROLE;
GRANT CREATE FILE FORMAT ON SCHEMA BOLIVIA_REAL_STATE.RAW TO ROLE DBT_DEV_ROLE;

-- Optional: only if dbt should create new schemas
GRANT CREATE SCHEMA ON DATABASE BOLIVIA_REAL_STATE TO ROLE DBT_DEV_ROLE;

-- Optional source read example
-- GRANT USAGE ON DATABASE <source_database> TO ROLE DBT_DEV_ROLE;
-- GRANT USAGE ON SCHEMA <source_database>.<source_schema> TO ROLE DBT_DEV_ROLE;
-- GRANT SELECT ON ALL TABLES IN SCHEMA <source_database>.<source_schema> TO ROLE DBT_DEV_ROLE;
-- GRANT SELECT ON FUTURE TABLES IN SCHEMA <source_database>.<source_schema> TO ROLE DBT_DEV_ROLE;
```

Set these values in .env to match:
- SNOWFLAKE_ROLE=DBT_DEV_ROLE
- SNOWFLAKE_WAREHOUSE=<your_warehouse>
- DEV_DATABASE=BOLIVIA_REAL_STATE
- SCHEMA=RAW

## Validation
After replacing placeholders and applying grants:

```bash
uv run dbt debug --project-dir dbt_project_1
```

If validation fails, check:
- Role name and warehouse name in `.env`
- Network policy / IP allowlist in Snowflake
- User default role or explicit role permissions
