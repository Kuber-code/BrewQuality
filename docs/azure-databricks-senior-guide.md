# Azure Databricks — senior cheat-sheet (with the details they probe for)

A focused, opinionated map of how Azure Databricks actually works and the
"smaczki" that signal you've operated it, not just read the brochure. Anchored
to this project (BrewQuality) so every concept has a concrete referent.

---

## 1. The mental model: control plane vs data plane

This is the answer that separates seniors from tutorial-followers.

- **Control plane** (Databricks-managed, in Databricks' Azure subscription): the
  web app, notebooks, job scheduler, cluster manager, Unity Catalog metastore
  metadata. You never run compute here.
- **Data plane / compute plane**: where clusters actually run and where your
  data lives. In **classic** compute the VMs run **in your subscription** (your
  VNet, your quota, your bill); in **serverless** they run in a Databricks-managed
  network. Your data sits in **your ADLS Gen2** either way.

Why it matters: networking, data residency, and cost all hinge on this split.
"The compute runs in my subscription, the data never leaves my storage, the
control plane only holds metadata" is the sentence to have ready.

## 2. Compute — clusters, jobs, serverless, DBUs

- **All-purpose cluster**: interactive, for notebooks/dev. Stays up; expensive if
  left running.
- **Jobs cluster**: created for a scheduled job, torn down after. **Cheaper** for
  automated pipelines — this is what BrewQuality's Workflow uses.
- **Serverless**: instant start, scales to zero, no VM management; Databricks runs
  the compute. Great DX, but classic gives you VNet control and (often) is the
  only option under a low Free-Trial quota.
- **Single-node**: driver only, `num_workers: 0` + `spark.master local[*]`. Cheapest
  viable shape — what we use here to fit the trial's small vCPU quota.
- **DBU vs VM cost** (the #1 cost gotcha): you pay **two** things — the cloud
  **VM** (compute) *and* the **DBU** (Databricks' per-second software charge) on
  top. Right-sizing the VM isn't enough; DBU rate varies by workload type
  (Jobs < All-purpose < SQL) and tier (Standard/Premium).
- **Photon**: the vectorized C++ engine — big speedups for SQL/Delta scans, higher
  DBU rate; worth it for heavy SQL, not for tiny jobs.
- **Autoscaling + pools**: autoscale workers between min/max; **instance pools**
  keep warm VMs so clusters start in seconds instead of minutes (latency smaczek).
- **Spot/preemptible** workers cut cost on the worker tier; keep the driver
  on-demand so a preemption doesn't kill the job.

## 3. Unity Catalog — governance (the role's core)

- **Metastore**: an **account-level** object (one per region, attached to many
  workspaces). It is *not* deleted when you delete a workspace/resource group —
  remember this for teardown.
- **Three-level namespace**: `catalog.schema.table`. We use **one catalog per
  environment** (`brewquality_dev/staging/prod`) for isolation, schemas
  `bronze/silver/gold/quarantine/ops`.
- **Managed vs external tables**:
  - *Managed* — UC owns metadata **and** the files (in the metastore's managed
    storage). Drop the table → files deleted. Gets **predictive optimization**
    (auto OPTIMIZE/VACUUM).
  - *External* — UC owns metadata; files live at a path **you** control via an
    **external location**. Drop the table → files remain.
- **Storage credential + external location**: a *storage credential* wraps an
  Azure identity (our **Access Connector / Managed Identity**); an *external
  location* binds a credential to an `abfss://` path. Access to ADLS is brokered
  through these — **no account keys scattered in code**. This is the BrewQuality
  auth story end-to-end.
- **Lineage**: automatic, **table- and column-level**, once data flows through UC.
  It's the incident-runbook's "trace upstream which table changed" step — no
  instrumentation needed.
- **Grants**: `GRANT SELECT ON SCHEMA ...` etc. We give analysts `gold`+`ops`
  only; engineers own the pipeline schemas. Least privilege, centrally.
- **Access modes** (a real gotcha): UC needs a **Single-user** or **Shared**
  access-mode cluster. "No isolation" legacy clusters can't use UC. Shared mode
  historically restricted some Spark APIs (RDD, some UDFs) — know this if a job
  "works on my single-user cluster but not the shared one".

## 4. Storage & identity — ADLS Gen2, MI vs SP, Key Vault

- **ADLS Gen2** = Blob + **hierarchical namespace** (real directories, atomic
  dir ops, POSIX ACLs) — the standard lakehouse storage layer.
- **Account keys** → avoid at runtime (long-lived, over-privileged, leak risk).
- **Service Principal** → a non-human identity for **automation/CI-CD** (our
  `sp-brewquality-cicd` is the deploy identity). Has a secret to rotate.
- **Managed Identity** → Azure-managed, **no secret to store/rotate**; preferred
  when the workload runs in Azure. Our **Access Connector** is exactly this, used
  for UC→ADLS.
- **Key Vault-backed secret scope**: notebooks read secrets via
  `dbutils.secrets.get(scope, key)`; the scope is backed by Key Vault so the
  secret never appears in code or Git. Map from AWS: SP/MI ≈ IAM roles,
  Key Vault ≈ Secrets Manager.

## 5. Asset Bundles (DAB) + CI/CD — your DevOps edge

- **DAB = IaC for Databricks**: `databricks.yml` declares jobs, clusters, and
  libraries; `databricks bundle deploy -t <target>` ships them reproducibly per
  environment. It replaces click-ops — same mindset as Terraform.
- **Targets** map to environments (dev/staging/prod) and here to UC catalogs.
- **Artifacts**: DAB builds the project **wheel** and installs it on the job, so
  the cluster runs the *same tested code* as CI (`brewquality.dq`).
- **`development` vs `production` mode**: dev prefixes resource names and pauses
  schedules so parallel devs don't collide; prod deploys clean.
- **CI/CD flow**: PR → lint + `pytest` + `bundle validate` → deploy staging →
  integration run (assert DQ metrics) → manual-approval promote to prod, deploying
  as the **Service Principal**, environments isolated by catalog.

## 6. Delta smaczki (storage-format details seniors drop)

- **Small-file problem** → `OPTIMIZE` compacts; **`ZORDER BY`** co-locates by a
  filtered column for data skipping. **Liquid clustering** (`CLUSTER BY`) is the
  newer, maintenance-free alternative to partitioning + ZORDER.
- **`VACUUM`** deletes unreferenced files older than the retention window
  (default 7 days) — it **destroys time travel** beyond that, so weigh audit needs
  before shortening it.
- **Time travel** (`VERSION AS OF` / `TIMESTAMP AS OF`, `RESTORE`) — diff a bad
  load against the prior good version during an incident.
- **Deletion vectors** — mark rows deleted without rewriting files (merge-on-read);
  faster `DELETE`/`UPDATE`/`MERGE`, compacted later.
- **`MERGE`** for upserts/CDC; **`CHECK`/`NOT NULL` constraints** as a write-time
  backstop behind the application DQ gate.
- **AQE** (Adaptive Query Execution) handles skew/partition coalescing at runtime —
  let it, instead of hand-tuning `shuffle.partitions`.
- **Predictive optimization** — Databricks auto-runs OPTIMIZE/VACUUM on managed
  UC tables, so you stop scheduling maintenance jobs.

## 7. Observability without extra tooling

- **System tables** (`system.billing.usage`, `system.access.audit`,
  `system.compute...`) — query cost, audit, and lineage **as SQL**. "I track DBU
  spend and audit access from system tables" is a strong line.
- **Job run history + alerts**, **Spark UI** for stage/skew/shuffle diagnosis,
  and our `ops.dq_metrics` table for data-quality KPIs.

## 8. Free-Trial reality check

- You pay **DBU + VM** against the $200 credit — Databricks is **not free** even
  on trial. Keep one **single-node jobs cluster**, let it auto-terminate, and run
  **`scripts/azure_teardown.ps1`** when done.
- Trials often have a **low regional vCPU quota** (e.g. 4). A single-node
  `Standard_DS3_v2` (4 vCPU) fits; if cluster-start fails with a quota error,
  request an increase in *Subscription → Usage + quotas* (or shrink the VM).
- **Serverless** may be unavailable on a trial — classic single-node is the
  reliable path.

---

### 60-second interview pitch
"BrewQuality runs on Azure Databricks: data in ADLS Gen2, governed by Unity
Catalog with one catalog per environment, lineage and least-privilege grants.
Compute is a single-node **jobs** cluster that auto-terminates — I pay DBU plus
the VM only while it runs. Storage access is brokered by an **Access Connector
managed identity** via a UC storage credential, so there are **no account keys in
code**; the CI/CD deploy uses a **Service Principal** with its secret in **Key
Vault**. The pipeline ships as a **Databricks Asset Bundle** — jobs and clusters
as code, promoted dev→staging→prod — and the DQ gate quarantines bad rows and
writes KPIs I can alert on. Same PySpark/Delta code runs locally, in CI, and on
the platform."
