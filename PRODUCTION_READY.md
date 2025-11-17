# Production Readiness Guide

This document describes the production-ready improvements made to Brainda for stable personal deployment on Unraid.

## Overview

Brainda has been optimized for **single-user personal deployment** with focus on:
- ✅ System stability (resource limits, restart policies)
- ✅ Cost protection (circuit breakers, timeouts)
- ✅ Graceful shutdown (no data loss on restart)
- ✅ Easy updates (one-command update script)
- ✅ Code quality (pre-commit hooks)

---

## What Changed

### 1. **Docker Resource Limits** (docker-compose.prod.yml)

All containers now have resource limits to prevent consuming all Unraid server resources:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

**Total Resource Usage (Maximum):**
- **Orchestrator**: 2 CPU, 2GB RAM
- **Postgres**: 2 CPU, 2GB RAM
- **Qdrant**: 2 CPU, 2GB RAM
- **Worker**: 2 CPU, 2GB RAM
- **Redis**: 1 CPU, 768MB RAM
- **Beat**: 0.5 CPU, 512MB RAM
- **Total**: ~9.5 CPUs, ~9.5GB RAM (fits comfortably in 16GB system)

**Benefits:**
- Prevents memory leaks from crashing Unraid
- Fair resource sharing with other containers
- Predictable performance

---

### 2. **Auto-Restart on Failure** (docker-compose.prod.yml)

All containers now have `restart: unless-stopped`:

```yaml
restart: unless-stopped
```

**Benefits:**
- Containers restart automatically if they crash
- Survives Unraid server reboots
- No manual intervention needed

---

### 3. **Circuit Breakers for External APIs** (NEW)

**File:** `app/common/circuit_breaker.py`

Prevents runaway costs if external APIs fail or go crazy:

```python
# Circuit breaker wraps API calls
breaker = CircuitBreaker("openai", max_failures=5, reset_timeout=60)
result = await breaker.call(my_api_function)
```

**How it works:**
- Tracks API failures
- After 5 failures, stops making requests for 60 seconds
- Prevents waking up to surprise $1000 OpenAI bills
- Automatically recovers when service is healthy

**Protected Services:**
- OpenAI/Anthropic LLM calls
- OpenMemory API
- Google Calendar API (future)

**Configuration (.env):**
```bash
CIRCUIT_BREAKER_MAX_FAILURES=5      # Stop after 5 failures
CIRCUIT_BREAKER_RESET_TIMEOUT=60    # Try again after 60 seconds
```

---

### 4. **API Timeouts** (.env.example)

All external API calls now have timeouts to prevent hanging requests:

```bash
HTTP_TIMEOUT=30              # General HTTP requests
LLM_TIMEOUT=60               # LLM completions (longer for streaming)
GOOGLE_API_TIMEOUT=15        # Google Calendar API
OPENMEMORY_TIMEOUT=10        # OpenMemory API
```

**Benefits:**
- Requests don't hang forever
- Faster error detection
- Better user experience

---

### 5. **Graceful Shutdown** (entrypoint.sh)

Containers now shut down gracefully instead of being killed immediately:

```bash
trap shutdown TERM INT       # Catch shutdown signals
shutdown() {
  kill -TERM "$child_pid"    # Ask process to stop nicely
  wait "$child_pid"          # Wait for it to finish
}
```

**Benefits:**
- In-flight requests complete before shutdown
- Database connections close properly
- No data corruption on restart

---

### 6. **PostgreSQL Connection Pooling** (docker-compose.prod.yml)

Database now configured for better connection management:

```yaml
environment:
  POSTGRES_MAX_CONNECTIONS: 50
  POSTGRES_SHARED_BUFFERS: 256MB
```

**Benefits:**
- Better performance under load
- Efficient resource usage
- No connection exhaustion

---

### 7. **Redis Persistence** (docker-compose.prod.yml)

Redis now persists data to disk:

```yaml
command: redis-server --save 60 1000
volumes:
  - redis_data:/data
```

**Benefits:**
- Celery queue survives restarts
- No lost background tasks
- Idempotency keys preserved

---

### 8. **Simple Update Script** (update.sh)

One command to update Brainda:

```bash
./update.sh
```

**What it does:**
1. Pulls latest code from git
2. Rebuilds Docker containers
3. Restarts services
4. Runs health check
5. Shows running containers

**Benefits:**
- Easy updates
- No manual Docker commands
- Automatic health verification

---

### 9. **Pre-commit Hooks** (.pre-commit-config.yaml)

Optional code quality checks before commits:

```bash
# Install once
pip install pre-commit
pre-commit install

# Runs automatically on git commit
```

**What it checks:**
- Python code formatting (black)
- Import sorting (isort)
- Linting (flake8)
- Shell script syntax (shellcheck)
- Dockerfile best practices (hadolint)
- Trailing whitespace, file endings
- Private keys accidentally committed

---

## How to Use

### Initial Setup

1. **Update your .env file** with new timeout configurations:
```bash
# Copy new variables from .env.example
cp .env.example .env.new
# Merge your existing .env with new variables
```

2. **Rebuild containers** with new resource limits:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Regular Updates

Just run the update script:
```bash
./update.sh
```

### Optional: Enable Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Enable hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

---

## Monitoring

### Check Container Resource Usage

```bash
docker stats
```

### Check if Circuit Breakers Opened

```bash
docker compose logs orchestrator | grep circuit_breaker
```

Example output:
```
circuit_breaker_opened: Opening circuit breaker after 5 failures
circuit_breaker_open: Circuit breaker is open, rejecting request
circuit_breaker_recovered: Service recovered, closing circuit
```

### Check Health

```bash
curl http://localhost:8000/api/v1/health
```

---

## Configuration Reference

### Resource Limits (16GB RAM System)

Current limits are optimized for a 16GB RAM Unraid server with multiple containers. Adjust if needed:

**For 32GB+ RAM systems:**
```yaml
# Increase limits in docker-compose.prod.yml
limits:
  cpus: '4.0'
  memory: 4G
```

**For 8GB RAM systems:**
```yaml
# Decrease limits
limits:
  cpus: '1.0'
  memory: 1G
```

### Circuit Breaker Settings

**Conservative (prevent costs):**
```bash
CIRCUIT_BREAKER_MAX_FAILURES=3
CIRCUIT_BREAKER_RESET_TIMEOUT=120
```

**Aggressive (prefer availability):**
```bash
CIRCUIT_BREAKER_MAX_FAILURES=10
CIRCUIT_BREAKER_RESET_TIMEOUT=30
```

---

## Troubleshooting

### Container Keeps Restarting

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs orchestrator

# Check resource usage
docker stats vib-orchestrator

# Increase memory limit if OOM (Out of Memory)
```

### Circuit Breaker is Open

```bash
# Check why API is failing
docker compose -f docker-compose.prod.yml logs orchestrator | grep -A 5 circuit_breaker

# Manually reset (restart container)
docker compose -f docker-compose.prod.yml restart orchestrator
```

### Update Script Fails

```bash
# Check git status
git status

# Manually update
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### Pre-commit Hook Fails

```bash
# Run hooks manually to see errors
pre-commit run --all-files

# Skip hooks temporarily (not recommended)
git commit --no-verify
```

---

## What's NOT Included

Since this is a **personal single-user deployment**, the following enterprise features are intentionally NOT included:

- ❌ High availability / clustering
- ❌ Load balancing
- ❌ Advanced monitoring dashboards (Grafana)
- ❌ Alerting (you'll notice if it's down)
- ❌ CI/CD pipelines
- ❌ Security scanning (less critical for personal use)
- ❌ Rate limiting (you won't DDoS yourself)
- ❌ Multiple environments
- ❌ Off-site backups (handled by Unraid)

These can be added later if needed, but aren't necessary for personal use.

---

## Cloudflare Tunnel Integration

Since you're using Cloudflare Tunnel for remote access, you already have:

- ✅ HTTPS/TLS encryption
- ✅ Zero-trust security
- ✅ DDoS protection
- ✅ WAF (Web Application Firewall)
- ✅ No exposed ports

**No additional HTTPS/reverse proxy setup needed!**

---

## Next Steps (Optional)

1. **Test the update script:**
```bash
./update.sh
```

2. **Enable pre-commit hooks** (if you want code quality checks):
```bash
pip install pre-commit
pre-commit install
```

3. **Monitor resource usage** for a few days:
```bash
docker stats
```

4. **Adjust resource limits** if needed based on actual usage

---

## Support

If you encounter issues:

1. Check logs: `docker compose -f docker-compose.prod.yml logs -f`
2. Check resource usage: `docker stats`
3. Check health: `curl http://localhost:8000/api/v1/health`
4. Check circuit breakers: `docker compose logs | grep circuit_breaker`

For questions, check CLAUDE.md or ask Claude Code for help!
