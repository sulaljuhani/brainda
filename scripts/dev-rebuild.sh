#!/bin/bash
set -e

echo "🏗️  Rebuilding containers (use only when dependencies change)..."

# Build with cache (much faster than --no-cache)
DOCKER_BUILDKIT=1 docker compose -f docker-compose.yml -f docker-compose.dev.yml build

echo "✅ Rebuild complete!"
echo "💡 Tip: You only need to rebuild when you change:"
echo "   - requirements.txt (Python dependencies)"
echo "   - package.json (Node dependencies)"
echo "   - System packages in Dockerfile"
echo ""
echo "For code changes, just save the file - auto-reload will handle it!"
