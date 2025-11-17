# Docker Quick Start

## Development (Hot Reload) 🔥
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```
- Frontend: http://localhost:3000 ✅ Hot reload
- Backend: http://localhost:8000 ✅ Hot reload

## Production (Optimized Build) 🚀
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
- Everything: http://localhost:8000 (single endpoint)

## Common Commands

```bash
# View logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# Stop services
docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# Rebuild after dependency changes
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build frontend orchestrator
```

**See DOCKER_SETUP.md for full documentation**
