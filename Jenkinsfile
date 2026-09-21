pipeline {
    agent any

    environment {
        // Cần thiết lập credentials trong Jenkins với ID là 'dockerhub-credentials'
        // Type: Username with password
        DOCKERHUB_CREDENTIALS = credentials('dockerhub-credentials')
        DOCKER_IMAGE = 'nhangdinhh/smart-erp-seafood'
        DOCKER_TAG = 'latest'
    }

    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "Building Docker image ${DOCKER_IMAGE}:${DOCKER_TAG}..."
                    sh "docker build -t ${DOCKER_IMAGE}:${DOCKER_TAG} ."
                }
            }
        }

        stage('Push to DockerHub') {
            steps {
                script {
                    echo "Logging into DockerHub..."
                    sh "echo \$DOCKERHUB_CREDENTIALS_PSW | docker login -u \$DOCKERHUB_CREDENTIALS_USR --password-stdin"
                    
                    echo "Pushing Docker image..."
                    sh "docker push ${DOCKER_IMAGE}:${DOCKER_TAG}"
                }
            }
        }

        stage('Deploy to Render') {
            steps {
                script {
                    echo "Since the project is using Render, it will auto-deploy via DockerHub Webhooks."
                    echo "Render will pull the latest image and restart the service."
                    // Nếu bạn có Render Deploy Hook URL, có thể dùng curl để trigger thủ công tại đây:
                    // sh "curl -X POST https://api.render.com/deploy/srv-xxxxx?key=yyyyyy"
                }
            }
        }
    }

    post {
        always {
            echo "Cleaning up..."
            sh "docker logout"
        }
        success {
            echo '🎉 Pipeline completed successfully!'
        }
        failure {
            echo '❌ Pipeline failed. Please check the Jenkins console logs.'
        }
    }
}
