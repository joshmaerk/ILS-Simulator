@description('Azure AI Foundry Hub name')
param hubName string

@description('Azure AI Foundry Project name')
param projectName string

param location string
param tags object

@description('Key Vault resource ID (associated with hub for secret storage)')
param keyVaultId string

// ============================================================
// AI Hub (workspace)
// ============================================================
resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: hubName
  location: location
  tags: tags
  kind: 'Hub'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Manager-AI Foundry Hub'
    friendlyName: 'Manager AI Hub'
    keyVault: keyVaultId
    publicNetworkAccess: 'Enabled'
  }
}

// ============================================================
// AI Project (child of hub)
// ============================================================
resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: projectName
  location: location
  tags: tags
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Manager-AI multi-agent project'
    friendlyName: 'Manager AI'
    hubResourceId: aiHub.id
    publicNetworkAccess: 'Enabled'
  }
}

// ============================================================
// Azure OpenAI Service (connected to hub)
// Note: In Azure AI Foundry, OpenAI is provisioned as a
// connected resource. Model deployments are managed via the
// AI Foundry portal or the azure-ai-projects SDK after deployment.
// ============================================================
resource openAIAccount 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: '${hubName}-oai'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${hubName}-oai'
    publicNetworkAccess: 'Enabled'
  }
}

// gpt-4o deployment
resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAIAccount
  name: 'gpt-4o'
  sku: {
    name: 'GlobalStandard'
    capacity: 80  // 80K TPM
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
  }
}

// gpt-4o-mini deployment (for routing)
resource gpt4oMiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAIAccount
  name: 'gpt-4o-mini'
  dependsOn: [gpt4oDeployment]
  sku: {
    name: 'GlobalStandard'
    capacity: 100
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
    }
  }
}

// ============================================================
// Outputs
// ============================================================
output hubId string = aiHub.id
output hubName string = aiHub.name
output projectId string = aiProject.id
output projectName string = aiProject.name
// The project endpoint follows this pattern; actual value available after deployment
output projectEndpoint string = 'https://${hubName}.services.ai.azure.com/api/projects/${projectName}'
output openAIEndpoint string = openAIAccount.properties.endpoint
// Bing connection ID must be configured manually in AI Foundry portal and referenced here
output bingConnectionId string = '${aiProject.id}/connections/bing-search'
