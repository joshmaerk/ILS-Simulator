@description('Key Vault name')
param name string

param location string
param tags object

@secure()
param botAppPassword string

@secure()
param graphClientSecret string

@description('AAD Object ID of the manager user (for Key Vault access policy)')
param managerUserId string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenant().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: false  // set true for prod
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Bot App Password secret
resource botPasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'bot-app-password'
  properties: {
    value: botAppPassword
    attributes: {
      enabled: true
    }
  }
}

// Graph Client Secret
resource graphSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'graph-client-secret'
  properties: {
    value: graphClientSecret
    attributes: {
      enabled: true
    }
  }
}

// RBAC: Key Vault Administrator for the manager user (for manual secret management)
resource managerKvAdmin 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managerUserId, 'KeyVaultAdmin')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00482a5a-887f-4fb3-b363-3b7fe8e74483') // Key Vault Administrator
    principalId: managerUserId
    principalType: 'User'
  }
}

output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output botPasswordSecretUri string = botPasswordSecret.properties.secretUri
output graphSecretUri string = graphSecret.properties.secretUri
