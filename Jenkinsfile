pipeline {
    agent {
        kubernetes {
            defaultContainer 'python'
            yamlFile 'k8s-agent.yaml'
        }
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        ansiColor('xterm')
    }

    stages {
        stage('Checkout source code') {
            steps {
                dir('scenario') {
                    git(
                        branch: 'phucnt',
                        credentialsId: 'github-ssh',
                        url: 'git@github.com:ELCOM-PRIME/Scenario.git'
                    )
                }
            }
        }

        stage('Install dependencies') {
            steps {
                dir('scenario') {
                    sh '''
                        apt-get update
                        apt-get install -y --no-install-recommends \
                            gcc \
                            libpq-dev \
                            python3-dev

                        python --version
                        python -m pip install --upgrade pip

                        if [ -f requirements.txt ]; then
                            python -m pip install -r requirements.txt
                        fi

                        python -m pip install pytest
                    '''
                }
            }
        }

        stage('Run tests') {
            steps {
                dir('scenario') {
                    sh '''
                        python -m pytest tests/ -v
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'All tests passed.'
        }

        failure {
            echo 'CI failed. Check the logs for details.'
        }
    }
}