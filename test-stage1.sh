#!/bin/bash
set -e

TOKEN=${API_TOKEN:-"default-token-change-me"}
if [ "$TOKEN" = "default-token-change-me" ] && [ -f ".env" ]; then
  ENV_TOKEN=$(grep -E '^API_TOKEN=' .env | tail -n 1 | cut -d '=' -f2-)
  if [ -n "$ENV_TOKEN" ]; then
    TOKEN=$ENV_TOKEN
  fi
fi

echo "Testing Stage 1: Chat + Notes + Vector"
echo "======================================"

echo "Waiting for orchestrator to be healthy (up to 60s)..."
for i in {1..30}; do
  if curl -sf http://localhost:8003/api/v1/health | jq -e '.status == "healthy"' > /dev/null 2>&1; then
    echo ""
    echo "✓ Orchestrator is healthy!"
    break
  fi
  echo -n "."
  sleep 2
done
if ! curl -sf http://localhost:8003/api/v1/health | jq -e '.status == "healthy"' > /dev/null 2>&1; then
    echo "✗ Orchestrator did not become healthy in time."
    curl -s http://localhost:8003/api/v1/health | jq
    exit 1
fi
echo ""

# Test 1: Create note
echo "Test 1: Creating note..."
NOTE=$(curl -sf -X POST http://localhost:8003/api/v1/notes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "TestNote", "body": "Hello VIB", "tags": ["test"]}')
NOTE_ID=$(echo $NOTE | jq -r '.data.id')
MD_PATH=$(echo $NOTE | jq -r '.data.md_path')
echo "Created note: $NOTE_ID"
echo ""

# Test 2: Verify file exists
echo "Test 2: Checking file..."
if [ -f "vault/$MD_PATH" ]; then
    echo "✓ File created"
else
    echo "✗ File not found!"
    exit 1
fi
echo ""

# Test 3: Wait for embedding
echo "Test 3: Waiting for embedding (up to 2 minutes)..."
EMBEDDING_READY=0
for i in {1..12}; do
  docker exec vib-postgres psql -U vib -d vib -t -c \
    "SELECT embedding_model FROM file_sync_state WHERE file_path = '${MD_PATH}';" \
    | grep -q "all-MiniLM-L6-v2:1" && EMBEDDING_READY=1 && break
  sleep 10
done
if [ $EMBEDDING_READY -eq 1 ]; then
  echo "✓ Embedding detected"
else
  echo "✗ Embedding not ready after waiting"
  exit 1
fi
echo ""

# Test 4: Check file_sync_state (final confirmation)
echo "Test 4: Checking sync state..."
docker exec vib-postgres psql -U vib -d vib -t -c \
  "SELECT embedding_model FROM file_sync_state WHERE file_path = '${MD_PATH}';" \
  | grep "all-MiniLM-L6-v2:1" || exit 1
echo "✓ Sync state updated"
echo ""

# Test 5: Search
echo "Test 5: Testing search..."
RESULTS=$(curl -sf "http://localhost:8003/api/v1/search?q=hello" \
  -H "Authorization: Bearer $TOKEN")
echo $RESULTS | grep -i testnote || exit 1
echo "✓ Search working"
echo ""

# Test 6: Deduplication
echo "Test 6: Testing deduplication..."
NOTE2=$(curl -sf -X POST http://localhost:8003/api/v1/notes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "TestNote", "body": "Hello VIB again", "tags": ["test"]}')
DEDUPED=$(echo $NOTE2 | jq -r '.deduplicated')
if [ "$DEDUPED" = "true" ]; then
    echo "✓ Deduplication working"
else
    echo "✗ Deduplication failed"
    exit 1
fi
echo ""

echo "======================================"
echo "✅ Stage 1 validation complete!"
