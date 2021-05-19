String[] containerRuntimes = ["podman", "docker"]


pipeline {
    agent {
        label "sle-desktop-bci-tester"
    }
    stages {
        stage("tests") {
            parallel {
                stage ("format") {
                    steps {
                        script {
                            sh "tox -e format -- --check --diff"
                        }
                    }
                }

                stage("unit tests") {
                    steps {
                        script {
                            sh "tox -e list-all"
                            sh "tox -e unit"
                        }
                    }
                }

                stage("fetch containers") {
                    steps {
                        script {
                            for (containerRuntime in containerRuntimes) {
                                sh "CONTAINER_RUNTIME=${containerRuntime} tox -e fetch-all"
                            }
                        }
                    }
                }
            }
        }

        stage("test containers") {
            steps {
                script {
                    toxEnvs = sh (
                        script: "tox -l",
                        returnStdout: true
                    ).trim().split("\n").findAll{ it != "unit" && it != "fetch-all" && it != "list-all" }

                    for (containerRuntime in containerRuntimes) {
                        for (toxEnv in toxEnvs) {
                            stage("${toxEnv} for ${containerRuntime}") {
                                try {
                                    sh "CONTAINER_RUNTIME=${containerRuntime} tox -e ${toxEnv}"
                                } catch (ex) {
                                    unstable("Test of the container ${toxEnv} for ${containerRuntime} failed")
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            junit "junit_**.xml"
            sh 'podman rm -af; podman rmi -af'
            sh 'docker ps -a -q|xargs docker rm -f || :; docker image prune -af'
        }
        failure {
            mail to: 'dcermak@suse.com',
                subject: "Failed Pipeline: ${currentBuild.fullDisplayName}",
                body: "Build failed in ${env.BUILD_URL}"
        }
    }
}
