@description('App Service Plan name')
param planName string

@description('App Service name')
param appName string

param location string
param tags object

param keyVaultName string
param cosmosEndpoint string
param aiProjectEndpoint string
param botAppId string
param graphClientId string
param graphTenantId string
param bingConnectionId string

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: 'B2'
    tier: 'Basic'
  }
  properties: {
    reserved: true  // required for Linux
  }
}

resource appService 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  tags: tags
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'  // Managed Identity for service-to-service auth
  }
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      alwaysOn: true
      ftpsState: 'Disabled'
      http20Enabled: true
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: aiProjectEndpoint
        }
        {
          name: 'AZURE_OPENAI_DEPLOYMENT'
          value: 'gpt-4o'
        }
        {
          name: 'AZURE_OPENAI_MINI_DEPLOYMENT'
          value: 'gpt-4o-mini'
        }
        {
          name: 'BING_CONNECTION_ID'
          value: bingConnectionId
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosEndpoint
        }
        {
          name: 'COSMOS_DATABASE'
          value: 'manager-ai'
        }
        {
          name: 'GRAPH_TENANT_ID'
          value: graphTenantId
        }
        {
          name: 'GRAPH_CLIENT_ID'
          value: graphClientId
        }
        // Key Vault references for secrets
        {
          name: 'GRAPH_CLIENT_SECRET'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=graph-client-secret)'
        }
        {
          name: 'BOT_APP_ID'
          value: botAppId
        }
        {
          name: 'BOT_APP_PASSWORD'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=bot-app-password)'
        }
        {
          name: 'ENVIRONMENT'
          value: 'production'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
      ]
    }
    httpsOnly: true
  }
}

output appName string = appService.name
output defaultHostname string = appService.properties.defaultHostName
output principalId string = appService.identity.principalId
