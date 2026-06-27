# Tear down EVERYTHING this project created in Azure, to stop the credit burn.
# Run this when you're done demoing.
#
#   pwsh scripts/azure_teardown.ps1
#
# Deletes the resource group (workspace, storage, Key Vault, Access Connector),
# purges the soft-deleted Key Vault, and removes the Service Principal.
param(
  [string]$Rg     = "rg-brewquality",
  [string]$SpName = "sp-brewquality-cicd"
)
$ErrorActionPreference = "Continue"

# Key Vault soft-delete: capture name before the RG goes, then purge after.
$kvName = az keyvault list -g $Rg --query "[0].name" -o tsv 2>$null

Write-Host "Deleting resource group $Rg (this removes workspace, storage, KV, connector)..."
az group delete -n $Rg --yes | Out-Null

if ($kvName) {
  Write-Host "Purging soft-deleted Key Vault $kvName..."
  az keyvault purge -n $kvName 2>$null | Out-Null
}

Write-Host "Deleting Service Principal $SpName..."
$appId = az ad sp list --display-name $SpName --query "[0].appId" -o tsv 2>$null
if ($appId) { az ad sp delete --id $appId 2>$null | Out-Null }

Write-Host "Done. Note: a Unity Catalog *metastore* is an account-level object and"
Write-Host "is not deleted with the RG; remove external locations/credentials in the"
Write-Host "account console if you created a standalone metastore."
