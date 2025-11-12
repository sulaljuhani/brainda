# Development Guide

This guide explains the optimized development workflow for the BrainDA project.

## Quick Start

### Initial Setup (First Time Only)
```bash
# Clone the repository (if not already cloned)
git clone https://github.com/sulaljuhani/brainda
cd brainda

# Copy your environment file
cp /path/to/your/.env .

# Build containers (first time only)
DOCKER_BUILDKIT=1 docker compose -f docker-compose.yml -f docker-compose.dev.yml build

# Start services
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

## Daily Development Workflow

### For Code Changes (Most Common - FAST!)

#### If editing code directly on the server:
```bash
# Just save your files - changes auto-reload!
# No need to rebuild or restart anything!
```

#### If using GitHub workflow (Edit → Commit → Pull):
```bash
# 1. Edit code on your local machine
# 2. Commit and push to GitHub
# 3. On the server, pull and restart:
./scripts/pull-and-restart.sh
```

This script:
- Pulls latest changes from GitHub
- Detects if dependencies changed (auto-suggests rebuild)
- Restarts containers (takes ~10 seconds for code-only changes)
- No rebuild needed unless dependencies changed!

The development setup mounts your code as volumes, so pulled changes are immediately available:
- **FastAPI**: Auto-reloads on Python file changes
- **Celery Worker**: Restarts tasks on code changes
- **Frontend**: npm handles hot-reload

### For Dependency Changes (Occasional - MEDIUM Speed)
When you modify `requirements.txt` or `package.json`:

```bash
./scripts/dev-rebuild.sh
```

This rebuilds containers but uses cache, taking ~2-5 minutes instead of 20+ minutes.

### For Git Updates (When Pulling Changes)

**Recommended: Use the smart pull script**
```bash
./scripts/pull-and-restart.sh
```
This automatically detects dependency changes and suggests rebuild if needed.

**Alternative: Manual approach**
```bash
git pull origin your-branch
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart
```

This pulls latest code and restarts containers (no rebuild needed unless dependencies changed).

### For Complete Reset (Rare - SLOW)
Only when you need to clear all data and start fresh:

```bash
./scripts/full-reset.sh
```

⚠️ This deletes all database data, vectors, uploads, etc.

## What Changed from Your Old Workflow?

### ❌ Old Workflow (20+ minutes)
```bash
docker compose down -v --remove-orphans
rm -rf workspace
git clone ...
docker compose build --no-cache  # ← Rebuilds EVERYTHING from scratch!
docker compose up -d
```

### ✅ New Development Workflow (<10 seconds for code changes!)
```bash
# Edit your Python/JS files
# Save
# Done! Changes auto-reload!
```

### ✅ New Rebuild Workflow (2-5 minutes when dependencies change)
```bash
./scripts/dev-rebuild.sh  # Uses cache + BuildKit mounts
```

## Performance Comparison

| Scenario | Old Workflow | New Workflow | Time Saved |
|----------|--------------|--------------|------------|
| Code change | 20+ min (full rebuild) | <10 sec (auto-reload) | ~20 min |
| Dependency change | 20+ min (--no-cache) | 2-5 min (cached build) | 15-18 min |
| Git pull | 20+ min (delete + reclone) | <30 sec (pull + restart) | 19+ min |

## How It Works

### Volume Mounting for Development
The `docker-compose.dev.yml` file mounts your local code into the containers:

```yaml
services:
  orchestrator:
    volumes:
      - ./app:/app  # Your code is mounted, not copied!
```

This means:
1. You edit files on your host machine
2. Changes appear instantly inside containers
3. FastAPI/Celery detect changes and reload automatically
4. **No rebuild needed!**

### BuildKit Cache Mounts
The Dockerfile uses BuildKit cache mounts:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
```

This means:
1. Downloaded packages are cached between builds
2. Even with `--no-cache`, pip doesn't re-download packages
3. Rebuilds are 3-5x faster

### Layer Ordering Optimization
Dependencies are installed before code is copied:

```dockerfile
# System packages (rarely change) - Layer 1
RUN apt-get install nodejs npm ...

# Python dependencies (occasionally change) - Layer 2
COPY requirements.txt ...
RUN pip install -r requirements.txt

# Node dependencies (occasionally change) - Layer 3
COPY package.json ...
RUN npm install

# Application code (changes frequently) - Layer 4
COPY app/ /app/
```

Docker caches each layer. Changing code only invalidates Layer 4!

## Common Commands

### View Logs
```bash
# All services
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# Specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f orchestrator
```

### Restart a Service
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart orchestrator
```

### Run Commands Inside Container
```bash
# Python shell
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec orchestrator python

# Bash shell
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec orchestrator bash
```

### Run Tests
```bash
./test-mvp-complete.sh
```

## Production Builds

For production, use the standard commands (not the dev override):

```bash
# Production build (with cache)
DOCKER_BUILDKIT=1 docker compose build

# Production build (no cache, for clean builds)
DOCKER_BUILDKIT=1 docker compose build --no-cache
```

## Troubleshooting

### Changes Not Reflecting?
1. Check if the file is actually mounted (not a new file in a non-mounted directory)
2. Check container logs for syntax errors preventing reload
3. Try restarting the specific service

### "Module not found" Error After Dependency Change?
You need to rebuild:
```bash
./scripts/dev-rebuild.sh
```

### Weird Database State?
Reset just the database:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down postgres
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
```

Or full reset:
```bash
./scripts/full-reset.sh
```

## Tips

1. **Keep containers running**: Don't stop them between coding sessions
2. **Use logs to debug**: `docker compose logs -f` shows you auto-reload messages
3. **Only rebuild when necessary**: Dependencies changed? Rebuild. Code changed? Just save.
4. **Use production setup for final testing**: Before deploying, test with production docker-compose
5. **Commit often**: Since you're not deleting the directory anymore, use git properly!

## Environment Variables

Make sure your `.env` file contains all required variables:
```bash
DATABASE_URL=postgresql://user:pass@postgres:5432/db
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
API_TOKEN=your-secret-token
LOG_LEVEL=INFO
POSTGRES_USER=user
POSTGRES_PASSWORD=pass
POSTGRES_DB=db
```

## Next Steps

- Consider using `docker compose watch` for even better hot-reload (Docker Compose v2.22+)
- Set up IDE integration for remote debugging into containers
- Create custom scripts for your specific testing workflows
