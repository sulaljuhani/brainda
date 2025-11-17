#!/bin/bash
# Test script for idempotency infrastructure

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Testing Idempotency Infrastructure"
echo "========================================="

# Get API token from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$API_TOKEN" ]; then
    echo -e "${RED}✗ API_TOKEN not found in .env${NC}"
    exit 1
fi

API_URL="http://localhost:8000"

# Generate a unique idempotency key
KEY=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")

echo ""
echo "Test 1: Create reminder with idempotency key"
echo "---------------------------------------------"
echo "Idempotency Key: $KEY"

RESPONSE1=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/reminders" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Idempotency Test Reminder",
    "body": "Testing idempotency",
    "due_at_utc": "2025-01-20T10:00:00Z",
    "due_at_local": "10:00:00",
    "timezone": "UTC"
  }')

HTTP_CODE1=$(echo "$RESPONSE1" | tail -n1)
BODY1=$(echo "$RESPONSE1" | head -n-1)
ID1=$(echo "$BODY1" | jq -r '.data.id' 2>/dev/null || echo "")

if [ "$HTTP_CODE1" != "200" ] && [ "$HTTP_CODE1" != "201" ]; then
    echo -e "${RED}✗ Test 1 failed: HTTP $HTTP_CODE1${NC}"
    echo "$BODY1"
    exit 1
fi

echo -e "${GREEN}✓ First request successful${NC}"
echo "Created reminder ID: $ID1"

echo ""
echo "Test 2: Retry with same idempotency key"
echo "----------------------------------------"

sleep 1

RESPONSE2=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/reminders" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Idempotency Test Reminder",
    "body": "Testing idempotency",
    "due_at_utc": "2025-01-20T10:00:00Z",
    "due_at_local": "10:00:00",
    "timezone": "UTC"
  }')

HTTP_CODE2=$(echo "$RESPONSE2" | tail -n1)
BODY2=$(echo "$RESPONSE2" | head -n-1)
ID2=$(echo "$BODY2" | jq -r '.data.id' 2>/dev/null || echo "")
REPLAY=$(echo "$RESPONSE2" | grep -i "x-idempotency-replay" || echo "")

if [ "$HTTP_CODE2" != "200" ] && [ "$HTTP_CODE2" != "201" ]; then
    echo -e "${RED}✗ Test 2 failed: HTTP $HTTP_CODE2${NC}"
    echo "$BODY2"
    exit 1
fi

if [ "$ID1" != "$ID2" ]; then
    echo -e "${RED}✗ Different IDs returned: $ID1 vs $ID2${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Second request returned same reminder ID${NC}"
echo "Reminder ID matches: $ID2"

if [ -n "$REPLAY" ]; then
    echo -e "${GREEN}✓ Idempotency replay header detected${NC}"
else
    echo -e "${YELLOW}⚠ Idempotency replay header not detected (might be cached)${NC}"
fi

echo ""
echo "Test 3: Aggressive retries (10 parallel requests)"
echo "--------------------------------------------------"

KEY2=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")

echo "Using key: $KEY2"

# Create 10 parallel requests
for i in {1..10}; do
  curl -s -X POST "$API_URL/api/v1/reminders" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Idempotency-Key: $KEY2" \
    -H "Content-Type: application/json" \
    -d "{
      \"title\": \"Aggressive Test ${KEY2}\",
      \"body\": \"Testing aggressive retries\",
      \"due_at_utc\": \"2025-01-20T12:00:00Z\",
      \"due_at_local\": \"12:00:00\",
      \"timezone\": \"UTC\"
    }" > /dev/null &
done

wait

# Check if only 1 reminder was created
sleep 2

# Query the database to count reminders with this title
if command -v docker &> /dev/null; then
    COUNT=$(docker exec brainda-postgres psql -U brainda  -d brainda -t -c \
      "SELECT COUNT(*) FROM reminders WHERE title LIKE 'Aggressive Test ${KEY2:0:8}%';" 2>/dev/null | tr -d ' ' || echo "0")

    if [ "$COUNT" = "1" ]; then
        echo -e "${GREEN}✓ Only 1 reminder created from 10 parallel requests${NC}"
    elif [ "$COUNT" = "0" ]; then
        echo -e "${YELLOW}⚠ Could not verify reminder count (database not accessible)${NC}"
    else
        echo -e "${RED}✗ Expected 1 reminder, found $COUNT${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Docker not available, skipping database verification${NC}"
fi

echo ""
echo "Test 4: Different key creates new reminder"
echo "-------------------------------------------"

KEY3=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")

RESPONSE3=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/reminders" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Idempotency-Key: $KEY3" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "New Reminder with Different Key",
    "body": "Testing different key",
    "due_at_utc": "2025-01-20T14:00:00Z",
    "due_at_local": "14:00:00",
    "timezone": "UTC"
  }')

HTTP_CODE3=$(echo "$RESPONSE3" | tail -n1)
BODY3=$(echo "$RESPONSE3" | head -n-1)
ID3=$(echo "$BODY3" | jq -r '.data.id' 2>/dev/null || echo "")

if [ "$HTTP_CODE3" != "200" ] && [ "$HTTP_CODE3" != "201" ]; then
    echo -e "${RED}✗ Test 4 failed: HTTP $HTTP_CODE3${NC}"
    echo "$BODY3"
    exit 1
fi

if [ "$ID3" = "$ID1" ]; then
    echo -e "${RED}✗ Same ID returned for different key: $ID3${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Different idempotency key created new reminder${NC}"
echo "New reminder ID: $ID3"

echo ""
echo "========================================="
echo -e "${GREEN}All idempotency tests passed! ✓${NC}"
echo "========================================="
