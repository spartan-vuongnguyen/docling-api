@Library('atrix@master') _

makeBuildPipeline {
  serviceConfigurations = [
    name              : 'doc-parser',
    clusterNamePrefix : 'atrix-eks-',
    helmRepo          : 'spartan',
    chartPath         : 'spartan/spartan',
    chartVersion      : '1.1.3'
  ]

  dockerFilePath = '/'
  dockerFileName = 'Dockerfile'

  nodeBuildLabel = 'heavy'

  helmStageTimeout = 30

  testCommand = 'jenkins-test'

  informStageEnabled = false

  codeQualityStageEnabled = false

  promoteImageEnabled = true

  devDeploymentEnabled = { ctx, buildEnv ->
      buildEnv.getBranchName() == "main"
  }

  additionalContainerConfig = { ctx, buildEnv ->
    if (buildEnv.isPullRequestBuild()) {
      []
    } else {
      [
        kaniko: [:]
      ]
    }
  }

  helmValuesPath = { ctx, buildEnv ->
    if (buildEnv.isDevDeploymentEnabled()) {
      'k8s/dev/values.yaml'
    } else if (buildEnv.isProdDeploymentEnabled()) {
      'k8s/prod/values.yaml'
    } else {
      ctx.error 'unknown environment!! Abort!!'
    }
  }
}
