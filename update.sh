#!/usr/bin/env bash
#
# Brainda Update Script
# ---------------------
# Simple script to pull latest changes and restart services
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "  Brainda Update Script"
echo "================================================"
echo ""

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
  echo -e "${GREEN}✓${NC} $*"
}

warn() {
  echo -e "${YELLOW}⚠${NC} $*"
}

error() {
  echo -e "${RED}✗${NC} $*"
}

# Check if we're in a git repository
if [ ! -d ".git" ]; then
  error "Not a git repository. Please run from the brainda project root."
  exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  warn "You have uncommitted changes:"
  git status --short
  echo ""
  read -p "Continue anyway? (y/N): " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Update cancelled."
    exit 0
  fi
fi

# Pull latest changes
echo ""
log "Pulling latest changes from git..."
if git pull; then
  log "Git pull successful"
else
  error "Git pull failed. Please resolve manually."
  exit 1
fi

# Check which compose file to use
COMPOSE_FILE="docker-compose.prod.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
  COMPOSE_FILE="docker-compose.yml"
  warn "Using docker-compose.yml (development mode)"
else
  log "Using $COMPOSE_FILE (production mode)"
fi

# Rebuild and restart services
echo ""
log "Rebuilding and restarting containers..."
if docker compose -f "$COMPOSE_FILE" up -d --build; then
  log "Containers rebuilt and restarted successfully"
else
  error "Docker compose failed. Check logs with: docker compose -f $COMPOSE_FILE logs"
  exit 1
fi

# Wait for health checks
echo ""
log "Waiting for services to become healthy..."
sleep 10

# Check orchestrator health
if curl -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
  log "Health check passed"
else
  warn "Health check failed. Check logs with: docker compose -f $COMPOSE_FILE logs orchestrator"
fi

# Show running containers
echo ""
log "Running containers:"
docker compose -f "$COMPOSE_FILE" ps

echo ""
log "Update complete!"
echo ""
echo "Useful commands:"
echo "  View logs:      docker compose -f $COMPOSE_FILE logs -f orchestrator"
echo "  Check status:   docker compose -f $COMPOSE_FILE ps"
echo "  Restart:        docker compose -f $COMPOSE_FILE restart"
echo "  Stop:           docker compose -f $COMPOSE_FILE down"
echo ""
