
resource codeinterpreter 'Microsoft.App/sessionPools@2025-01-01' = {
  name: 'code-interpreter'
  location: 'West Us 3'
  properties: {
    poolManagementType: 'Dynamic'
    containerType: 'PythonLTS'
    scaleConfiguration: {
      maxConcurrentSessions: 100
    }
    dynamicPoolConfiguration: {
      lifecycleConfiguration: {
        lifecycleType: 'Timed'
        cooldownPeriodInSeconds: 300
      }
    }
    sessionNetworkConfiguration: {
      status: 'EgressEnabled'
    }
  }
}
