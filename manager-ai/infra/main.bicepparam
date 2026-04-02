using './main.bicep'

// Fill in your values before deploying
param environmentName = 'dev'
param location = 'germanywestcentral'
param managerUserId = '<your-aad-object-id>'
param botAppId = '<your-bot-app-registration-client-id>'
param botAppPassword = '<your-bot-app-password>'  // use az keyvault secret or pipeline variable
param graphClientId = '<your-graph-app-registration-client-id>'
param graphClientSecret = '<your-graph-client-secret>'  // use pipeline variable
param aadTenantId = '<your-tenant-id>'
