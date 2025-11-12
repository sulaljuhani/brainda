#!/bin/bash
set -e

echo "⚠️  FULL RESET - This will delete all data!"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted"
    exit 1
fi

echo "🗑️  Stopping and removing containers and volumes..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans

echo "🏗️  Rebuilding from scratch..."
DOCKER_BUILDKIT=1 docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache

echo "🚀 Starting services..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

echo "✅ Full reset complete!"
echo "⚠️  Note: Use this sparingly - prefer dev-update.sh or dev-rebuild.sh"
