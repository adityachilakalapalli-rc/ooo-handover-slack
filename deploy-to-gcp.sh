#!/bin/bash

# GCP OOO Handover Slack App Deployment Script
# This script deploys the backend to Google Cloud Run

set -e

# Configuration
PROJECT_ID="roo-rc-ooo-handover"
SERVICE_NAME="ooo-handover-slack"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying OOO Handover Slack App to Google Cloud Run"
echo "=================================================="
echo "Project ID: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"
echo "Image: $IMAGE_NAME"
echo ""

# Step 1: Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Step 2: Set the project
echo "📝 Setting GCP project..."
gcloud config set project ${PROJECT_ID}

# Step 3: Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable containerregistry.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Step 4: Build Docker image
echo "🐳 Building Docker image..."
gcloud builds submit --tag ${IMAGE_NAME}:latest

# Step 5: Deploy to Cloud Run
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --memory 512Mi \
  --timeout 3600 \
  --set-env-vars="SLACK_SIGNING_SECRET=${SLACK_SIGNING_SECRET},SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN},GOOGLE_SERVICE_ACCOUNT_JSON=${GOOGLE_SERVICE_ACCOUNT_JSON},SPREADSHEET_ID=1CXANEZxW4UMzrjZQ7xliekchNCk3XTWZa-qQrWZeItc" \
  --allow-unauthenticated

# Step 6: Get the service URL
echo ""
echo "✅ Deployment Complete!"
echo ""
echo "Getting service URL..."
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
echo ""
echo "🎉 Your app is live at:"
echo "   $SERVICE_URL"
echo ""
echo "Update Slack app with these URLs:"
echo "  Slash Commands:    ${SERVICE_URL}/slack/commands"
echo "  Interactivity:     ${SERVICE_URL}/slack/interactivity"
echo "  Message Options:   ${SERVICE_URL}/slack/options"
