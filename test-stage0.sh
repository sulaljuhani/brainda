#!/bin/bash
set -e

echo "Testing Stage 0: Infrastructure & Deployment Foundation"
echo "======================================================="
echo ""

# Load token from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

TOKEN=${API_TOKEN:-"default-token-change-me"}

# Test 1: Health check
echo "Waiting for services to start..."
sleep 10
echo "Test 1: Health check..."
HEALTH=$(curl -sf http://localhost:8003/api/v1/health || echo "FAILED")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✓ Health check passed"
else
    echo "✗ Health check failed"
    echo "$HEALTH"
    exit 1
fi
echo ""

# Test 2: Metrics endpoint
echo "Test 2: Metrics endpoint..."
METRICS=$(curl -sf http://localhost:8003/api/v1/metrics || echo "FAILED")
if echo "$METRICS" | grep -q "# HELP"; then
    echo "✓ Metrics endpoint working"
else
    echo "✗ Metrics endpoint failed"
    exit 1
fi
echo ""

# Test 3: Auth with valid token
echo "Test 3: Auth with valid token..."
RESPONSE=$(curl -sf -H "Authorization: Bearer $TOKEN" http://localhost:8003/api/v1/protected || echo "FAILED")
if echo "$RESPONSE" | grep -q "Access granted"; then
    echo "✓ Valid token accepted"
else
    echo "✗ Valid token rejected"
    echo "$RESPONSE"
    exit 1
fi
echo ""

# Test 4: Auth with invalid token
echo "Test 4: Auth with invalid token..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer wrong-token" http://localhost:8003/api/v1/protected)
if [ "$STATUS" = "401" ]; then
    echo "✓ Invalid token rejected"
else
    echo "✗ Invalid token not rejected (got status $STATUS)"
    exit 1
fi
echo ""

# Test 5: Auth with no token
echo "Test 5: Auth with no token..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8003/api/v1/protected)
if [ "$STATUS" = "401" ]; then
    echo "✓ Missing token rejected"
else
    echo "✗ Missing token not rejected (got status $STATUS)"
    exit 1
fi
echo ""

# Test 6: Database tables
echo "Test 6: Database initialization..."
TABLES=$(docker exec vib-postgres psql -U vib -d vib -t -c "\dt" 2>/dev/null | grep -E "users|devices|feature_flags" | wc -l)
if [ "$TABLES" -ge 3 ]; then
    echo "✓ Database tables created"
else
    echo "✗ Database tables missing (found $TABLES, expected 3)"
    exit 1
fi
echo ""

# Test 7: Structured logging...
echo "Test 7: Structured logging..."
LOGS=$(docker logs vib-orchestrator 2>&1 | tail -5)
if echo "$LOGS" | grep -q "timestamp"; then
    echo "✓ Logs are JSON formatted"
else
    echo "✗ Logs are not JSON formatted"
    echo "$LOGS"
fi
echo ""

# Test 8: Redis
echo "Test 8: Redis connectivity..."
REDIS=$(docker exec vib-redis redis-cli ping 2>/dev/null || echo "FAILED")
if [ "$REDIS" = "PONG" ]; then
    echo "✓ Redis working"
else
    echo "✗ Redis not working"
    exit 1
fi
echo ""

# Test 9: Qdrant
echo "Test 9: Qdrant connectivity..."
QDRANT=$(curl -sf http://localhost:6333/collections || echo "FAILED")
if echo "$QDRANT" | grep -q "collections"; then
    echo "✓ Qdrant working"
else
    echo "✗ Qdrant not working"
    exit 1
fi
echo ""

# Test 10: Celery worker
echo "Test 10: Celery worker..."
docker exec vib-worker celery -A worker.tasks inspect active &>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Celery worker running"
else
    echo "⚠ Celery worker not responding (check logs)"
fi
echo ""

echo "======================================================="
echo "✅ Stage 0 validation complete!"
echo ""
echo "Next steps:"
echo " 1. Review logs: docker-compose logs"
echo " 2. Access health check: http://localhost:8003/api/v1/health"
echo " 3. Ready for Stage 1: Chat + Notes + Vector"
