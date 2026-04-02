// ============================================================
// Manager-AI – Main Bicep Template
// Deploys all Azure resources for the multi-agent management system
// ============================================================

targetScope = 'resourceGroup'

@description('Environment name (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environmentName string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Unique name suffix to avoid global naming conflicts')
param nameSuffix string = uniqueString(resourceGroup().id)

@description('AAD Object ID of the manager user (for RBAC)')
param managerUserId string

@description('Bot App Registration Client ID')
param botAppId string

@description('Bot App Registration Password (stored in Key Vault)')
@secure()
param botAppPassword string

@description('Azure AD App Registration Client ID for Microsoft Graph')
param graphClientId string

@description('Azure AD App Registration Client Secret for Microsoft Graph')
@secure()
param graphClientSecret string

@description('Azure AD Tenant ID')
param aadTenantId string = tenant().tenantId

// ============================================================
// Variables
// ============================================================
var prefix = 'mgrai-${environmentName}'
var tags = {
  project: 'manager-ai'
  environment: environmentName
  managedBy: 'bicep'
}

// ============================================================
// Key Vault (deploy first – other modules reference it)
// ============================================================
module keyVault 'modules/key-vault.bicep' = {
  name: 'keyVault'
  params: {
    name: '${prefix}-kv-${nameSuffix}'
    location: location
    tags: tags
    botAppPassword: botAppPassword
    graphClientSecret: graphClientSecret
    managerUserId: managerUserId
  }
}

// ============================================================
// Cosmos DB
// ============================================================
module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'cosmosDb'
  params: {
    accountName: '${prefix}-cosmos-${nameSuffix}'
    location: location
    tags: tags
  }
}

// ============================================================
// Azure AI Foundry (Hub + Project + model deployments)
// ============================================================
module aiFoundry 'modules/ai-foundry.bicep' = {
  name: 'aiFoundry'
  params: {
    hubName: '${prefix}-hub-${nameSuffix}'
    projectName: '${prefix}-project'
    location: location
    tags: tags
    keyVaultId: keyVault.outputs.keyVaultId
  }
}

// ============================================================
// App Service (hosts the bot)
// ============================================================
module appService 'modules/app-service.bicep' = {
  name: 'appService'
  params: {
    planName: '${prefix}-plan-${nameSuffix}'
    appName: '${prefix}-bot-${nameSuffix}'
    location: location
    tags: tags
    keyVaultName: keyVault.outputs.keyVaultName
    cosmosEndpoint: cosmosDb.outputs.endpoint
    aiProjectEndpoint: aiFoundry.outputs.projectEndpoint
    botAppId: botAppId
    graphClientId: graphClientId
    graphTenantId: aadTenantId
    bingConnectionId: aiFoundry.outputs.bingConnectionId
  }
}

// ============================================================
// Azure Bot Service
// ============================================================
module botService 'modules/bot-service.bicep' = {
  name: 'botService'
  params: {
    botName: '${prefix}-bot-${nameSuffix}'
    location: 'global'
    tags: tags
    botAppId: botAppId
    messagingEndpoint: 'https://${appService.outputs.defaultHostname}/api/messages'
  }
}

// ============================================================
// RBAC: App Service Managed Identity -> Cosmos DB
// ============================================================
resource cosmosRbac 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-02-15-preview' = {
  name: '${cosmosDb.outputs.accountName}/00000000-0000-0000-0000-000000000002'
  properties: {
    roleDefinitionId: '${resourceGroup().id}/providers/Microsoft.DocumentDB/databaseAccounts/${cosmosDb.outputs.accountName}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: appService.outputs.principalId
    scope: cosmosDb.outputs.accountId
  }
}

// ============================================================
// RBAC: App Service Managed Identity -> Key Vault Secrets User
// ============================================================
resource kvSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.outputs.keyVaultId, appService.outputs.principalId, 'KeyVaultSecretsUser')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: appService.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================
// RBAC: App Service Managed Identity -> AI Foundry (Azure AI Developer)
// ============================================================
resource aiDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiFoundry.outputs.hubId, appService.outputs.principalId, 'AzureAIDeveloper')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee') // Azure AI Developer
    principalId: appService.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================
// Outputs
// ============================================================
output botEndpoint string = 'https://${appService.outputs.defaultHostname}/api/messages'
output cosmosEndpoint string = cosmosDb.outputs.endpoint
output aiProjectEndpoint string = aiFoundry.outputs.projectEndpoint
output keyVaultName string = keyVault.outputs.keyVaultName
output appServiceName string = appService.outputs.appName
