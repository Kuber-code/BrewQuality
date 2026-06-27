# Provision the Azure footprint for BrewQuality on Azure Databricks.
# Idempotent-ish: safe to re-run; existing resources are left as-is.
# Prereq: `az login` and the right subscription selected.
#
#   pwsh scripts/azure_provision.ps1
#
# Footprint (minimal, Free-Trial friendly):
#   resource group, ADLS Gen2 (HNS) storage, Databricks workspace (premium),
#   Access Connector (system-assigned Managed Identity), Key Vault, and a
#   Service Principal for CI/CD. Auth model: Managed Identity for UC->ADLS,
#   Service Principal for deploys. No account keys are used at runtime.
param(
  [string]$Location   = "westeurope",
  [string]$Rg         = "rg-brewquality",
  [string]$Workspace  = "dbw-brewquality",
  [string]$AccessConn = "ac-brewquality",
  [string]$SpName     = "sp-brewquality-cicd"
)
$ErrorActionPreference = "Stop"
$sfx     = -join ((48..57)+(97..122) | Get-Random -Count 6 | ForEach-Object {[char]$_})
$Storage = "stbrewq$sfx"        # 3-24 lowercase alnum, globally unique
$KeyVault= "kv-brewq-$sfx"      # globally unique
$Container = "lake"

az config set extension.use_dynamic_install=yes_without_prompt | Out-Null

foreach ($p in @("Microsoft.Databricks","Microsoft.Storage","Microsoft.KeyVault","Microsoft.ManagedIdentity")) {
  az provider register -n $p | Out-Null
}

az group create -n $Rg -l $Location | Out-Null

# ADLS Gen2 = StorageV2 + hierarchical namespace (real directories, POSIX ACLs).
az storage account create -n $Storage -g $Rg -l $Location `
  --sku Standard_LRS --kind StorageV2 --hns true --min-tls-version TLS1_2 | Out-Null
$key = az storage account keys list -g $Rg -n $Storage --query "[0].value" -o tsv
az storage fs create -n $Container --account-name $Storage --account-key $key | Out-Null

# Access Connector = a managed identity Unity Catalog uses to reach ADLS.
az databricks access-connector create -n $AccessConn -g $Rg -l $Location `
  --identity-type SystemAssigned | Out-Null
$miPrincipal = az databricks access-connector show -n $AccessConn -g $Rg --query identity.principalId -o tsv
$storageId   = az storage account show -n $Storage -g $Rg --query id -o tsv

# Grant the MI (and you) data-plane access to the lake — no account keys at runtime.
az role assignment create --assignee-object-id $miPrincipal --assignee-principal-type ServicePrincipal `
  --role "Storage Blob Data Contributor" --scope $storageId | Out-Null
$me = az ad signed-in-user show --query id -o tsv
az role assignment create --assignee-object-id $me --assignee-principal-type User `
  --role "Storage Blob Data Contributor" --scope $storageId | Out-Null

az keyvault create -n $KeyVault -g $Rg -l $Location --enable-rbac-authorization false | Out-Null

# Service Principal as the CI/CD deploy identity; its secret lives only in Key Vault.
$rgId = az group show -n $Rg --query id -o tsv
$sp = az ad sp create-for-rbac -n $SpName --role Contributor --scopes $rgId -o json | ConvertFrom-Json
az keyvault secret set --vault-name $KeyVault -n "sp-cicd-client-secret" --value $sp.password | Out-Null
az keyvault secret set --vault-name $KeyVault -n "sp-cicd-client-id"     --value $sp.appId    | Out-Null
az keyvault secret set --vault-name $KeyVault -n "sp-cicd-tenant-id"     --value $sp.tenant   | Out-Null

# Workspace (premium = Unity Catalog + secret scopes). Takes ~8 minutes.
az databricks workspace create -n $Workspace -g $Rg -l $Location --sku premium | Out-Null
$wsUrl = az databricks workspace show -n $Workspace -g $Rg --query workspaceUrl -o tsv

Write-Host "Provisioned. Workspace: https://$wsUrl"
Write-Host "Storage=$Storage  KeyVault=$KeyVault  SP appId=$($sp.appId)  MI principal=$miPrincipal"
