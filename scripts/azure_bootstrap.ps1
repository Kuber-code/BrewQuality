# Configure everything INSIDE Databricks after azure_provision.ps1:
#   storage credential (managed identity) + external location  -> keyless ADLS
#   catalog + schemas + landing/libs volumes
#   Key-Vault-backed secret scope
#   upload the generated sample data to the landing volume
#
#   pwsh scripts/azure_bootstrap.ps1
#
# Prereq: `az login`, and .azure/env.ps1 from azure_provision.ps1.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
. "$repo\.azure\env.ps1"
$env:DATABRICKS_HOST = $WS_URL
$env:DATABRICKS_AUTH_TYPE = "azure-cli"
$enc = New-Object System.Text.UTF8Encoding($false)   # JSON files must be BOM-free
$tmp = Join-Path $env:TEMP "bq-bootstrap"; New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$catalog = "brewquality_dev"

function Write-Json($obj, $path) { [System.IO.File]::WriteAllText($path, ($obj | ConvertTo-Json -Depth 6), $enc) }

Write-Host "==> storage credential (managed identity via Access Connector)"
$acId = az databricks access-connector show -n $ACCESS_CONNECTOR -g $RG --query id -o tsv
Write-Json @{ name="brewquality_mi_cred"; comment="MI via Access Connector (no keys)"; azure_managed_identity=@{ access_connector_id=$acId } } "$tmp\cred.json"
databricks storage-credentials create --json "@$tmp\cred.json" | Out-Null

Write-Host "==> external location on the lake"
$lakeUrl = "abfss://$CONTAINER@$STORAGE.dfs.core.windows.net/"
Write-Json @{ name="brewquality_lake"; url=$lakeUrl; credential_name="brewquality_mi_cred"; comment="BrewQuality lakehouse root" } "$tmp\extloc.json"
databricks external-locations create --json "@$tmp\extloc.json" | Out-Null

Write-Host "==> catalog + schemas + volumes"
databricks catalogs create $catalog --storage-root "${lakeUrl}catalog" --comment "BrewQuality dev (UC over ADLS via MI)" | Out-Null
foreach ($s in @("bronze","silver","gold","quarantine","ops")) { databricks schemas create $s $catalog | Out-Null }
databricks volumes create $catalog bronze landing MANAGED | Out-Null
databricks volumes create $catalog ops libs MANAGED | Out-Null

Write-Host "==> Key-Vault-backed secret scope"
$DBX_APP = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"   # AzureDatabricks first-party app
if (-not (az ad sp show --id $DBX_APP --query appId -o tsv 2>$null)) { az ad sp create --id $DBX_APP | Out-Null }
az keyvault set-policy -n $KEYVAULT --spn $DBX_APP --secret-permissions get list | Out-Null
Write-Json @{ scope="brewquality-kv"; scope_backend_type="AZURE_KEYVAULT"; backend_azure_keyvault=@{ resource_id=$KV_ID; dns_name="https://$KEYVAULT.vault.azure.net/" } } "$tmp\scope.json"
databricks secrets create-scope --json "@$tmp\scope.json" | Out-Null

Write-Host "==> generate (if needed) + upload sample data to the landing volume"
if (-not (Test-Path "$repo\data\raw\orders.csv")) { Push-Location $repo; python -m brewquality.generate_data --orders 3000 --customers 300 --seed 42; Pop-Location }
$vol = "dbfs:/Volumes/$catalog/bronze/landing"
foreach ($f in @("orders.csv","customers.csv","products.json")) {
  databricks fs cp "$repo\data\raw\$f" "$vol/$f" --overwrite | Out-Null
}

Write-Host "done. Next: pwsh scripts/azure_deploy.ps1 -Run"
