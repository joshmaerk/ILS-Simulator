@description('Azure Bot resource name')
param botName string

@description('Must be "global" for Azure Bot Service')
param location string = 'global'

param tags object

@description('Bot App Registration Client ID')
param botAppId string

@description('HTTPS messaging endpoint of the App Service')
param messagingEndpoint string

resource azureBot 'Microsoft.BotService/botServices@2022-09-15' = {
  name: botName
  location: location
  tags: tags
  sku: {
    name: 'S1'  // S1 for production; F0 for free dev tier
  }
  kind: 'azurebot'
  properties: {
    displayName: 'Manager AI'
    description: 'Multi-agent management support system'
    iconUrl: 'https://docs.botframework.com/static/devportal/client/images/bot-framework-default.png'
    endpoint: messagingEndpoint
    msaAppId: botAppId
    msaAppType: 'SingleTenant'
    schemaTransformationVersion: '1.3'
    isStreamingSupported: false
  }
}

// Teams channel – enables the bot to receive Teams messages
resource teamsChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: azureBot
  name: 'MsTeamsChannel'
  location: location
  properties: {
    channelName: 'MsTeamsChannel'
    properties: {
      isEnabled: true
      enableCalling: false
    }
  }
}

output botId string = azureBot.id
output botName string = azureBot.name
output teamsChannelEnabled bool = true
