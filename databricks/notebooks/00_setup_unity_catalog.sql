-- Databricks notebook source
-- Unity Catalog setup — three-level namespace (catalog.schema.table), one
-- catalog per environment (dev/staging/prod) for isolation. Run once per env.
-- The :catalog parameter is supplied by the job / bundle target.

-- COMMAND ----------

CREATE CATALOG IF NOT EXISTS ${catalog};

-- Medallion layers as schemas; quarantine + ops sit alongside.
CREATE SCHEMA IF NOT EXISTS ${catalog}.bronze;
CREATE SCHEMA IF NOT EXISTS ${catalog}.silver;
CREATE SCHEMA IF NOT EXISTS ${catalog}.gold;
CREATE SCHEMA IF NOT EXISTS ${catalog}.quarantine;
CREATE SCHEMA IF NOT EXISTS ${catalog}.ops;

-- COMMAND ----------

-- Governance: least-privilege grants. BI/analysts read trusted layers only;
-- they never see raw bronze or quarantine. Engineers own the pipeline schemas.
GRANT USE CATALOG ON CATALOG ${catalog} TO `data-analysts`;
GRANT USE SCHEMA, SELECT ON SCHEMA ${catalog}.gold TO `data-analysts`;
GRANT USE SCHEMA, SELECT ON SCHEMA ${catalog}.ops  TO `data-analysts`;

GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.bronze     TO `data-engineers`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.silver     TO `data-engineers`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.gold       TO `data-engineers`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.quarantine TO `data-engineers`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.ops        TO `data-engineers`;

-- COMMAND ----------

-- Lineage is automatic in Unity Catalog once tables are read/written through it
-- (table- and column-level). It's what the incident runbook's "trace upstream"
-- step relies on — no extra config needed here.
