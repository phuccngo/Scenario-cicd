pipelineJob('scenario-python-ci') {

    definition {

        cpsScm {

            scm {

                git {

                    remote {
                        url('git@github.com:ELCOM-PRIME/Scenario-cicd.git')
                        credentials('github-ssh')
                    }

                    branch('*/phucnt')
                }
            }

            scriptPath('Jenkinsfile')
        }
    }
}