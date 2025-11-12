#!/bin/bash
set -e

echo "🔄 Updating codebase for development..."

# Pull latest changes (if in git repo)
if [ -d .git ]; then
    echo "📥 Pulling latest changes..."
    git pull origin $(git branch --show-current)
fi

# Copy environment file if needed
if [ -f /mnt/cache/appdata/code-server/workspace/.env ]; then
    echo "📋 Copying .env file..."
    cp /mnt/cache/appdata/code-server/workspace/.env .env
fi

# Only restart containers (no rebuild needed for code changes!)
echo "🔄 Restarting containers..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

echo "✅ Development environment updated and running!"
echo "📝 Code changes will now auto-reload without rebuilding!"
