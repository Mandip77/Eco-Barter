#!/bin/bash
# EcoBarter Deployment Script

set -e

echo "🚀 Starting EcoBarter Deployment..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file based on production.env before running this script."
    exit 1
fi

# Pull latest changes (optional, assuming script is run in the repo)
# git pull origin main

echo "🏗️ Building production images..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

echo "🚢 Starting services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "🧹 Cleaning up old images..."
docker image prune -f

echo "✅ Deployment successful!"
echo "Check logs with: docker compose logs -f"
