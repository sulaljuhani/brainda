#!/bin/bash
set -e

echo "🔄 Pulling latest changes from GitHub and restarting services..."

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Current branch: $CURRENT_BRANCH"

# Stash any local changes (shouldn't be any, but just in case)
if [[ -n $(git status -s) ]]; then
    echo "⚠️  Found local changes, stashing them..."
    git stash
fi

# Pull latest changes
echo "📥 Pulling latest changes..."
git pull origin "$CURRENT_BRANCH"

# Copy .env if needed (your specific setup)
if [ -f /mnt/cache/appdata/code-server/workspace/.env ]; then
    echo "📋 Updating .env file..."
    cp /mnt/cache/appdata/code-server/workspace/.env .env
fi

# Check if requirements.txt or package.json changed
DEPS_CHANGED=false
CHANGED_FILES=$(git diff --name-only HEAD@{1} HEAD 2>/dev/null || echo "")

if echo "$CHANGED_FILES" | grep -q "requirements.txt\|package.json"; then
    echo "⚠️  Dependencies changed! A rebuild is recommended."
    echo ""
    read -p "Rebuild containers? (y/n, default: y): " REBUILD
    REBUILD=${REBUILD:-y}

    if [ "$REBUILD" = "y" ] || [ "$REBUILD" = "Y" ]; then
        DEPS_CHANGED=true
    fi
fi

if [ "$DEPS_CHANGED" = true ]; then
    echo "🔨 Rebuilding containers with cache..."
    DOCKER_BUILDKIT=1 docker compose -f docker-compose.yml -f docker-compose.dev.yml build
    echo "🚀 Starting services..."
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
else
    echo "🔄 Restarting services (no rebuild needed)..."
    docker compose -f docker-compose.yml -f docker-compose.dev.yml restart
fi

echo ""
echo "✅ Services updated and running!"
echo ""
echo "📊 Container status:"
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps

echo ""
echo "💡 Tip: View logs with:"
echo "   docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f"
