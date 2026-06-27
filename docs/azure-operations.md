# Azure operations — cost control, stop, and rebuild

Everything you need to keep the Free-Trial credit safe and to bring the whole
environment back later. TL;DR: **idle costs almost nothing — you don't have to
tear down.** Only running compute burns credit.

---

## What actually costs money (and what doesn't)

| Resource | Idle cost | Notes |
|---|---|---|
| Databricks **workspace** | ~€0 | you pay **DBU only while compute runs** |
| **Serverless** job compute | €0 when not running | auto-stops after a job; no idle cost |
| **SQL warehouse** | €0 if none running | the evidence warehouse was **deleted**; serverless SQL auto-stops (1 min) |
| **ADLS Gen2** storage | a few cents/month | tiny dataset |
| **Key Vault** | ~€0 | per-operation pricing, negligible |
| **Access Connector / Managed Identity** | €0 | identity only |

**Conclusion:** with no job running and no always-on warehouse/cluster, the
environment costs roughly **storage cents per month**. The ~€30 already used was
provisioning + several debug job runs + the brief evidence warehouse — not an
ongoing drain. For a 30-day trial with €170 left, **leave it up** until after the
interview; just don't leave compute running.

## Soft "stop" (recommended for now) — verify nothing is running

```powershell
$env:DATABRICKS_HOST="https://adb-7405608746580780.0.azuredatabricks.net"
$env:DATABRICKS_AUTH_TYPE="azure-cli"
# Any SQL warehouses? (should be none — we deleted the evidence one)
databricks warehouses list -o json | ConvertFrom-Json | Select id,name,state
# Any all-purpose clusters running? (we use serverless jobs, so none expected)
databricks clusters list -o json | ConvertFrom-Json | Where-Object { $_.state -eq "RUNNING" } | Select cluster_name,state
```
If both are empty, you're at near-zero burn. Serverless job compute only spins up
when you run the job, and stops itself afterward — nothing to pause.

> The job's schedule is **PAUSED** in `databricks.yml`, so it won't fire on its own.

## Hard "stop" — full teardown (when you're done for good)

Deletes the resource group (workspace, storage, Key Vault, Access Connector),
purges the soft-deleted Key Vault, and removes the Service Principal:

```powershell
pwsh D:\Repos\BrewQuality\scripts\azure_teardown.ps1
```
After this, credit burn is exactly €0. Note: the Unity Catalog **metastore** is an
account-level object and survives RG deletion (it's free and shared per region).

## Rebuild everything from scratch (≈15 min, mostly the workspace)

Three commands. `az login` first; the scripts read/write `.azure/env.ps1`.

```powershell
az login                                         # pick the Free Trial subscription
pwsh scripts/azure_provision.ps1                 # RG, ADLS, workspace, MI, KV, SP  (~8-10 min)
pwsh scripts/azure_bootstrap.ps1                 # UC objects, secret scope, upload data
pwsh scripts/azure_deploy.ps1 -Run               # build wheel, deploy bundle, run the Workflow
```

What each does:
1. **`azure_provision.ps1`** — Azure resources (resource group, ADLS Gen2 with HNS,
   premium Databricks workspace, Access Connector managed identity, Key Vault,
   Service Principal). Writes new resource names to `.azure/env.ps1`.
2. **`azure_bootstrap.ps1`** — everything *inside* Databricks: storage credential +
   external location (the keyless MI path), catalog `brewquality_dev`, the five
   schemas, the landing + libs volumes, the Key-Vault-backed secret scope, and it
   uploads the generated sample data to the volume.
3. **`azure_deploy.ps1 -Run`** — builds the wheel, uploads it to the libs volume,
   `databricks bundle deploy -t dev`, and runs the Workflow end-to-end.

Expected result: `bronze_ingest`, `silver_dq_gate`, `gold_build` all **SUCCESS**;
~3040 bronze → ~2429 silver + ~611 quarantine (exact split varies with the data
seed).

## Re-checking the bill

Azure Portal → **Subscriptions → your trial → Cost analysis** (or `Cost Management`).
Filter by resource group `rg-brewquality` to see exactly what each resource spent.
