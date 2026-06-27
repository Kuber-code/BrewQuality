# Azure security setup (Phase 6)

How auth and storage work when BrewQuality runs on **Azure Databricks** — the
JD's explicit Azure surface: Key Vault, Service Principals, Managed Identities,
ADLS Gen2. Principle throughout: **no plaintext credentials in notebooks or Git**.

> This is a short "burst" on an Azure Free Trial ($200 / 30 days) — enough to
> stand it up, screenshot it, and document it. Maps 1:1 to AWS IAM
> roles / least-privilege, which I've used in production.

## What was actually provisioned (this is real, not a diagram)

Stood up with [`scripts/azure_provision.ps1`](../scripts/azure_provision.ps1),
torn down with [`scripts/azure_teardown.ps1`](../scripts/azure_teardown.ps1):

| Resource | Name | Role |
|---|---|---|
| Resource group | `rg-brewquality` (West Europe) | container for everything |
| ADLS Gen2 storage | `stbrewq…` (HNS on) + container `lake` | the Delta files |
| Databricks workspace | `dbw-brewquality` (premium) | the lakehouse |
| Access Connector | `ac-brewquality` (System-assigned MI) | UC→ADLS, **no keys** |
| Key Vault | `kv-brewq-…` | secret store |
| Service Principal | `sp-brewquality-cicd` | CI/CD deploy identity (secret in KV) |

Unity Catalog wiring: storage credential `brewquality_mi_cred` (the Access
Connector MI) → external location `brewquality_lake` → catalog `brewquality_dev`
with schemas bronze/silver/gold/quarantine/ops and a landing + libs volume. A
**Key-Vault-backed secret scope** `brewquality-kv` exposes vault secrets to
notebooks via `dbutils.secrets.get(...)` with nothing in code.

> **Compute note:** the job runs on **serverless** — this trial's classic VM SKUs
> were capacity-restricted (`SkuNotAvailable`), and serverless needs no VM sizing
> at all. The classic single-node alternative is kept (commented) in
> `databricks/databricks.yml`. See the deep-dive in
> [`azure-databricks-senior-guide.md`](azure-databricks-senior-guide.md).

## Storage — ADLS Gen2

Azure Data Lake Storage Gen2 = Blob storage with a **hierarchical namespace**
(real directories, POSIX-like ACLs, atomic directory ops) — the standard layer
under a lakehouse, holding the Delta files. Create a storage account with HNS
enabled and a container per environment.

## Identity — Service Principal vs Managed Identity

- **Service Principal** — a non-human app identity used for **CI/CD deploys** so
  pipelines don't run as a person. Holds least-privilege RBAC on the storage
  account (`Storage Blob Data Contributor` on the container).
- **Managed Identity** — Azure-managed, **no secret to store or rotate**;
  preferred when the workload itself runs in Azure. Use it for the workspace's
  access to storage where possible.

## Secrets — Key Vault-backed secret scope

Store any remaining secrets (e.g. the SP client secret) in **Azure Key Vault**,
then back a Databricks **secret scope** with it so notebooks read via
`dbutils.secrets.get(scope, key)` — never hardcoded:

```bash
databricks secrets create-scope brewquality-kv \
  --scope-backend-type AZURE_KEYVAULT \
  --resource-id <key-vault-resource-id> \
  --dns-name https://<vault>.vault.azure.net/
```

## Wiring it together — Unity Catalog external location

```sql
-- Storage credential brokers Azure identity; external location points at ADLS.
CREATE STORAGE CREDENTIAL brewquality_cred
  WITH AZURE_MANAGED_IDENTITY '<access-connector-resource-id>';

CREATE EXTERNAL LOCATION brewquality_lake
  URL 'abfss://lake@<account>.dfs.core.windows.net/'
  WITH (STORAGE CREDENTIAL brewquality_cred);
```

Notebooks/jobs then authenticate to ADLS via **OAuth** through the credential —
**zero account keys in code**. External tables live under this location; managed
tables use UC's managed storage.

## Checklist (what to screenshot for the portfolio)
- [ ] Storage account with hierarchical namespace enabled.
- [ ] Service Principal app registration + RBAC assignment.
- [ ] Key Vault + Databricks secret scope bound to it.
- [ ] UC storage credential + external location.
- [ ] A notebook reading from ADLS with **no secrets in the code**.
