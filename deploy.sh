#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# MUL Chatbot — GCP Cloud Run Deployment Script
# ═══════════════════════════════════════════════════════════════════
# Usage: bash deploy.sh
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - Docker installed and running
#   - .env file with your API keys
# ═══════════════════════════════════════════════════════════════════

set -e  # Exit on any error

# ── Configuration ─────────────────────────────────────────────────
PROJECT_ID="mul-agent-with-langgraph"         # ✅ Your GCP project ID
SERVICE_NAME="mul-chatbot"
REGION="asia-south1"                  # Mumbai — closest to Pakistan
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying MUL Chatbot to GCP Cloud Run..."
echo "   Project:  $PROJECT_ID"
echo "   Service:  $SERVICE_NAME"
echo "   Region:   $REGION"
echo ""

# ── Step 1: Set GCP project ───────────────────────────────────────
echo "📋 Step 1: Setting GCP project..."
gcloud config set project $PROJECT_ID

# ── Step 2: Enable required APIs ──────────────────────────────────
echo "🔧 Step 2: Enabling GCP APIs..."
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com \
  secretmanager.googleapis.com

# ── Step 3: Store secrets in GCP Secret Manager ───────────────────
echo "🔐 Step 3: Storing API keys in Secret Manager..."
# Load from local .env file
source .env

echo "$GOOGLE_API_KEY"    | gcloud secrets create GOOGLE_API_KEY    --data-file=- 2>/dev/null || \
echo "$GOOGLE_API_KEY"    | gcloud secrets versions add GOOGLE_API_KEY    --data-file=-

echo "$TAVILY_API_KEY"    | gcloud secrets create TAVILY_API_KEY    --data-file=- 2>/dev/null || \
echo "$TAVILY_API_KEY"    | gcloud secrets versions add TAVILY_API_KEY    --data-file=-

echo "$LANGCHAIN_API_KEY" | gcloud secrets create LANGCHAIN_API_KEY --data-file=- 2>/dev/null || \
echo "$LANGCHAIN_API_KEY" | gcloud secrets versions add LANGCHAIN_API_KEY --data-file=-

# ── Step 4: Build and push Docker image ───────────────────────────
echo "🐳 Step 4: Building and pushing Docker image..."
gcloud auth configure-docker --quiet
docker build -t $IMAGE .
docker push $IMAGE

# ── Step 5: Deploy to Cloud Run ───────────────────────────────────
echo "☁️  Step 5: Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --timeout 120 \
  --concurrency 80 \
  --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest,TAVILY_API_KEY=TAVILY_API_KEY:latest,LANGCHAIN_API_KEY=LANGCHAIN_API_KEY:latest" \
  --set-env-vars "LANGCHAIN_TRACING_V2=true,LANGCHAIN_PROJECT=mul-chatbot,ENV=production"

echo ""
echo "✅ Deployment complete!"
echo "🌐 Your chatbot is live at:"
gcloud run services describe $SERVICE_NAME --region $REGION --format "value(status.url)"
