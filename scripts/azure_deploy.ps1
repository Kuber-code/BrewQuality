# One-command deploy of BrewQuality to the Azure Databricks dev target.
# Rebuilds the wheel, uploads it to the UC libs volume (the serverless silver
# notebook %pip-installs it), deploys the bundle, and runs the Workflow.
#
#   pwsh scripts/azure_deploy.ps1
#
# Requires: `az login` done, and .azure/env.ps1 present (from azure_provision).
param(
  [string]$Target = "dev",
  [switch]$Run
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
. "$repo\.azure\env.ps1"
$env:DATABRICKS_HOST = $WS_URL
$env:DATABRICKS_AUTH_TYPE = "azure-cli"

Write-Host "==> building wheel"
Push-Location $repo
python -m build --wheel | Out-Null
$whl = Get-ChildItem "$repo\dist\brewquality-*.whl" | Sort-Object LastWriteTime | Select-Object -Last 1
Pop-Location

Write-Host "==> uploading wheel to UC volume"
$catalog = if ($Target -eq "dev") { "brewquality_dev" } elseif ($Target -eq "staging") { "brewquality_staging" } else { "brewquality_prod" }
databricks fs cp $whl.FullName "dbfs:/Volumes/$catalog/ops/libs/$($whl.Name)" --overwrite | Out-Null

Write-Host "==> bundle deploy -t $Target"
Push-Location "$repo\databricks"
databricks bundle deploy -t $Target
if ($Run) {
  Write-Host "==> bundle run"
  databricks bundle run brewquality_pipeline -t $Target
}
Pop-Location
Write-Host "done."
