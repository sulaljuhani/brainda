# VIB - Personal Knowledge Management System

VIB is a personal knowledge management system that combines note-taking, document ingestion, semantic search, and intelligent reminders. It features RAG (Retrieval Augmented Generation) capabilities for answering questions based on your stored knowledge.

## Features

- **Note Management**: Create, update, and organize notes with tags
- **Document Ingestion**: Upload and process documents (PDF, text, etc.) with automatic parsing
- **Semantic Search**: Vector-based search across notes and documents using embeddings
- **RAG Chat Interface**: Ask questions and get answers based on your knowledge base
- **Modern Chat UI**: Dark-mode chat surface with responsive navigation and tool-call visualization
- **Smart Reminders**: Schedule and manage reminders with natural language processing
- **Calendar Scheduling**: Create recurring events, view a weekly calendar, and link reminders to events
- **Push Notifications**: Web push notifications for reminders and updates
- **Metrics & Monitoring**: Prometheus metrics for system health and performance
- **Passkeys & TOTP Security**: Multi-user authentication with WebAuthn passkeys, session tokens, and backup TOTP codes

## MVP Requirement Coverage

The Stage 0-8 requirements documented in [`devloper_notes/README.md`](devloper_notes/README.md) map to the implementation as follows:

| Requirement | Implementation Highlights |
| --- | --- |
| Chat-first interface with streaming responses【F:devloper_notes/README.md†L23-L35】 | React prototype in `app/web/components/VibInterface.tsx` drives chat, notes, reminders, calendar, and search panes with tool-call visualization.【F:app/web/components/VibInterface.tsx†L798-L880】 |
| Simple authentication with API tokens (plus Stage 8 passkeys/TOTP)【F:devloper_notes/README.md†L25-L35】 | API validates bearer tokens and issues hashed session tokens via the auth service; passkey/TOTP routes extend login flows.【F:app/api/dependencies.py†L39-L101】【F:app/api/services/auth_service.py†L197-L257】 |
| Time-based reminders with deduplication【F:devloper_notes/README.md†L27-L35】 | Reminder service creates RRULE-aware reminders, links calendar events, and prevents duplicates via metrics-backed safeguards.【F:app/api/services/reminder_service.py†L15-L159】 |
| Notes stored as Markdown and exposed via unified vector search【F:devloper_notes/README.md†L28-L35】 | Note endpoints persist Markdown files and queue embeddings that feed semantic search through the vector service and RAG pipeline.【F:app/api/main.py†L717-L825】【F:app/api/services/rag_service.py†L12-L84】 |
| Document ingestion pipeline with deduping and background jobs【F:devloper_notes/README.md†L29-L35】 | Document router stores uploads under `/app/uploads`, deduplicates by SHA-256, and enqueues Celery jobs for embedding.【F:app/api/routers/documents.py†L1-L110】【F:app/api/services/document_service.py†L11-L139】 |
| Push notifications across Web/FCM/APNs with TTL + collapse keys【F:devloper_notes/README.md†L31-L35】 | Notification service fans out to Web Push, FCM, and APNs adapters, handling TTL, collapse IDs, and structured payloads.【F:app/api/services/notification_service.py†L1-L366】 |
| Metrics/observability for ingestion, reminders, chat, and health【F:devloper_notes/README.md†L32-L35】 | Prometheus registry exports business SLOs, ingestion counters, and infrastructure gauges via `/api/v1/metrics`.【F:app/api/metrics.py†L1-L198】 |

## Architecture

VIB consists of several microservices orchestrated with Docker Compose:

- **API Server** (FastAPI): Main application server
- **Worker** (Celery): Background task processing for embeddings and document ingestion
- **Beat** (Celery Beat): Scheduled task management
- **PostgreSQL**: Primary database for structured data
- **Redis**: Message broker and cache
- **Qdrant**: Vector database for semantic search
- **Web Frontend**: React-based user interface

## Prerequisites

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- **Git**
- At least **4GB RAM** available for Docker

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd brainda
```

### 2. Configure Environment Variables

Copy the example environment file and customize it:

```bash
cp .env.example .env
```

Edit `.env` and update the following variables:

```bash
# Database credentials
POSTGRES_USER=vib
POSTGRES_PASSWORD=<your-secure-password>
POSTGRES_DB=vib
DATABASE_URL=postgresql://vib:<your-secure-password>@postgres:5432/vib

# Redis
REDIS_URL=redis://redis:6379/0

# Qdrant
QDRANT_URL=http://qdrant:6333

# Authentication - Generate a secure token
API_TOKEN=<generate-with-openssl-rand-hex-32>

# Application
LOG_LEVEL=INFO
TZ=UTC

# LLM Backend (optional)
LLM_BACKEND=ollama  # dummy | ollama | openai | anthropic | custom
LLM_MODEL=placeholder-model

# Provider-specific settings
# Ollama
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3

# OpenAI
OPENAI_API_KEY=sk-your-openai-key
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_TOKENS=1024

# Custom (OpenAI-compatible)
CUSTOM_LLM_URL=https://api.your-llm.com/v1/chat/completions
CUSTOM_LLM_API_KEY=your-secret-key
CUSTOM_LLM_MODEL=your-model-v1
CUSTOM_LLM_HEADERS={"X-Organization": "your-org"}
```

Generate a secure API token:

```bash
openssl rand -hex 32
```

### 3. Create Required Directories

```bash
mkdir -p vault/notes uploads
```

### 4. Start the Services

```bash
docker compose up -d
```

This will start all services in detached mode. Initial startup may take several minutes as Docker downloads images and builds containers.

### 5. Verify Installation

Check that all services are healthy:

```bash
docker compose ps
```

All services should show status "Up" or "Up (healthy)".

Check the health endpoint:

```bash
curl http://localhost:8000/api/v1/health
```

You should see a JSON response with `"status": "healthy"` and all services marked as "ok".

### 6. Apply Stage 8 Migration

Run the Stage 8 SQL migration to create multi-user authentication tables:

```bash
docker compose exec vib-postgres \
  psql -U vib -d vib -f migrations/006_add_multi_user_auth.sql
```

Repeat this command on each environment when you deploy Stage 8.

## Usage

### Access the Application

- **API Base URL**: http://localhost:8000
- **Health Check**: http://localhost:8000/api/v1/health
- **Metrics**: http://localhost:8000/api/v1/metrics
- **API Docs**: http://localhost:8000/docs

### Modern UI Prototype

- The chat-first interface described in `devloper_notes/UI.md` is implemented in `app/web/components/VibInterface.tsx`.
- Import the component into your React shell (for example, a Vite or Next.js page) to preview the dark-mode layout, sidebar navigation, and streaming chat experience.
- Design tokens (color, typography, spacing) are defined via CSS custom properties at the top of the component so the visual system can be reused across additional screens.

### API Authentication

Stage 8 introduces session-based authentication with passkeys and TOTP. The API accepts:

- **Session tokens** issued by the passkey/TOTP login flow (stored as `session_token` in localStorage and IndexedDB)
- **Legacy API tokens** (`API_TOKEN`) for backward compatibility and automation scripts

Send either token as a Bearer credential:

```bash
curl -H "Authorization: Bearer YOUR_SESSION_OR_API_TOKEN" \
     http://localhost:8000/api/v1/protected
```

Legacy API tokens continue to work, but new users should register a passkey and rely on session tokens.

#### Passkey Endpoints

- `POST /api/v1/auth/register/begin` – start WebAuthn registration (returns options + challenge)
- `POST /api/v1/auth/register/complete` – verify attestation and persist the credential
- `POST /api/v1/auth/login/begin` – issue a WebAuthn authentication challenge
- `POST /api/v1/auth/login/complete` – verify assertion and create a 30-day session
- `POST /api/v1/auth/logout` – invalidate the current session token

#### TOTP Backup Endpoints

- `POST /api/v1/auth/totp/setup` – generate a secret, QR code, and hashed backup codes
- `POST /api/v1/auth/totp/verify` – confirm TOTP and enable the factor
- `POST /api/v1/auth/totp/authenticate` – sign in with a TOTP or backup code (issues a session token)

Front-end components `PasskeyRegister.tsx` and `PasskeyLogin.tsx` demonstrate how to call these endpoints from the browser.

### Google Calendar Synchronisation (Stage 7)

VIB can synchronise calendar events with Google Calendar once you register an OAuth2 client and provide credentials.

1. Create a Google Cloud project and enable the **Google Calendar API**.
2. Configure an OAuth2 client (application type **Web Application**) with the redirect URI `http://localhost:8000/api/v1/calendar/google/callback` (add your production URL as needed).
3. Copy the client ID/secret into `.env` alongside the following variables:

   ```bash
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/calendar/google/callback
   GOOGLE_OAUTH_STATE_SECRET=<random-64-byte-string>
   GOOGLE_TOKEN_ENCRYPTION_KEY=<output of Fernet.generate_key()>
   GOOGLE_OAUTH_SUCCESS_REDIRECT=http://localhost:3000/settings?success=google_connected
   GOOGLE_OAUTH_FAILURE_REDIRECT=http://localhost:3000/settings?error=google_auth_failed
   ```

4. Restart the API and worker containers so the new configuration is loaded.
5. Use the API (or frontend component) to connect a user and authorise Google Calendar access.

> **Security tip:** Generate the `GOOGLE_TOKEN_ENCRYPTION_KEY` with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and store secrets securely.

#### Relevant API Endpoints

- `GET /api/v1/calendar/google/connect` – start the OAuth flow (returns the Google consent URL).
- `GET /api/v1/calendar/google/callback` – OAuth redirect handler that stores tokens.
- `POST /api/v1/calendar/google/disconnect` – revoke local access and delete stored credentials.
- `GET /api/v1/calendar/google/status` – view connection state, direction, and last sync time.
- `POST /api/v1/calendar/google/sync` – enqueue an immediate sync job.
- `PATCH /api/v1/calendar/google/settings` – toggle one-way vs two-way sync.

Background Celery jobs (`worker.tasks.schedule_google_calendar_syncs`) dispatch per-user push/pull tasks every 15 minutes. You can override the debounce window with `GOOGLE_SYNC_DEBOUNCE_SECONDS` if needed.

### Creating Your First Note

```bash
curl -X POST http://localhost:8000/api/v1/notes \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Note",
    "body": "This is the content of my first note.",
    "tags": ["example", "tutorial"]
  }'
```

### Searching Your Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "search query here",
    "limit": 5
  }'
```

### Using the Chat Interface

Ask questions about your knowledge base:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are my notes about Python?"
  }'
```

Create notes via chat:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a note titled Meeting Notes with body Discussed project timeline"
  }'
```

Set reminders:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Remind me to review docs in 2 hours"
  }'
```

### Managing Calendar Events

Create a recurring event (with RRULE support):

```bash
curl -X POST http://localhost:8000/api/v1/calendar/events \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Weekly Review",
    "starts_at": "2025-01-13T17:00:00Z",
    "timezone": "UTC",
    "location_text": "Zoom",
    "rrule": "FREQ=WEEKLY;BYDAY=MO;COUNT=4"
  }'
```

List events for a weekly window (recurring instances are expanded):

```bash
START="2025-01-13T00:00:00Z"
END="2025-01-20T00:00:00Z"

curl "http://localhost:8000/api/v1/calendar/events?start=$START&end=$END" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

Link an existing reminder to a calendar event:

```bash
curl -X POST http://localhost:8000/api/v1/calendar/events/$EVENT_ID/reminders/$REMINDER_ID \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

The web prototype (`app/web/components/VibInterface.tsx`) now shows a weekly calendar panel next to chat, and the Expo mobile app (`vib-mobile/src/screens/CalendarScreen.tsx`) includes a dedicated **Calendar** tab.

## Development

### Running in Development Mode

For development with hot-reload:

```bash
# Start backend services
docker compose up -d postgres redis qdrant

# Run API server locally
cd app
export PYTHONPATH=$(pwd)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker (in another terminal)
celery -A worker.tasks worker --loglevel=info

# Run Celery beat (in another terminal)
celery -A worker.scheduler beat --loglevel=info

# Run web frontend (in another terminal)
cd app/web
npm install
npm run dev
```

### Running Tests

#### Test Prerequisites

The test suite requires the following additional dependencies:

- **jq** - Command-line JSON processor
- **curl** - HTTP client (usually pre-installed)
- **docker** - For database and service access
- **python3** or **bc** - For numeric comparisons

Install jq on your system:

```bash
# Ubuntu/Debian
sudo apt-get install jq

# RHEL/CentOS/Fedora
sudo yum install jq

# macOS
brew install jq

# Windows (via Chocolatey)
choco install jq
```

#### Running the Test Suite

Execute the comprehensive test suite:

```bash
# Run MVP complete tests
./test-mvp-complete.sh

# Run specific stage tests
./test-stage0.sh  # Basic health and metrics
./test-stage1.sh  # Notes and reminders
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f orchestrator
docker compose logs -f worker
docker compose logs -f postgres
```

## Configuration

### Database Migrations

Database schema is initialized automatically on first startup via `init.sql`. For incremental migrations:

```bash
docker exec vib-postgres psql -U vib -d vib -f /app/migrations/your_migration.sql
```

### Adjusting Resource Limits

Edit `docker-compose.yml` to adjust resource allocations:

```yaml
services:
  orchestrator:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

### Performance Tuning

Key environment variables for performance:

- `CHAT_RATE_LIMIT`: Maximum chat requests per window (default: 30)
- `CHAT_RATE_WINDOW_SECONDS`: Rate limit window in seconds (default: 60)
- `API_LATENCY_THRESHOLD`: API response time target in ms (default: 500)
- `SEARCH_LATENCY_THRESHOLD`: Search response time target in ms (default: 200)

## Troubleshooting

### Services Not Starting

Check Docker logs:
```bash
docker compose logs
```

Ensure ports are not already in use:
```bash
lsof -i :8000  # API
lsof -i :5434  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :6333  # Qdrant
```

### Database Connection Errors

Verify PostgreSQL is running and accepting connections:
```bash
docker compose exec postgres pg_isready -U vib
```

### Embedding Tasks Not Processing

Check Celery worker status:
```bash
docker compose logs worker
```

Verify Redis connectivity:
```bash
docker compose exec redis redis-cli ping
```

### Vector Search Not Working

Ensure Qdrant collection is created:
```bash
curl http://localhost:6333/collections
```

Check embedding model is downloaded:
```bash
docker compose logs orchestrator | grep "all-MiniLM-L6-v2"
```

## Project Structure

```
.
├── app/
│   ├── api/                    # FastAPI application
│   │   ├── adapters/          # External service adapters
│   │   ├── models/            # Pydantic models
│   │   ├── routers/           # API route handlers
│   │   ├── services/          # Business logic
│   │   ├── tools/             # Reusable tool implementations
│   │   └── main.py            # Application entry point
│   ├── common/                # Shared utilities
│   ├── web/                   # React frontend
│   └── worker/                # Celery tasks and scheduler
├── migrations/                # SQL migration files
├── tests/                     # Test scripts and fixtures
├── vault/                     # Note storage (markdown files)
├── uploads/                   # Uploaded document storage
├── docker-compose.yml         # Service orchestration
├── Dockerfile                 # Container build definition
└── README.md                  # This file
```

## Security Considerations

- **API Tokens**: Store API tokens securely, never commit to version control
- **Environment Files**: Keep `.env` files out of version control
- **Network Exposure**: By default, services are exposed on localhost only
- **Production Deployment**: Update CORS settings, use HTTPS, implement proper authentication
- **File Uploads**: Uploaded files are stored with restricted permissions (600)
- **Database**: Use strong passwords and restrict network access in production

## Contributing

See `AGENTS.md` for development guidelines, coding standards, and contribution workflow.

## License

[Add your license information here]

## Support

For issues and questions:
- Check the troubleshooting section above
- Review logs with `docker compose logs`
- Open an issue in the repository
### Configuring LLM Providers

Set `LLM_BACKEND` to choose which adapter powers Retrieval-Augmented Generation responses. The server includes native adapters for Ollama, OpenAI, Anthropic, and arbitrary OpenAI-compatible APIs.

| Backend | Required Settings | Notes |
| --- | --- | --- |
| `dummy` | None | Returns a placeholder response without calling an external model. Useful for development without API keys. |
| `ollama` | `OLLAMA_URL`, optional `OLLAMA_MODEL` | Streams responses from a local or remote Ollama deployment. |
| `openai` | `OPENAI_API_KEY`, optional `OPENAI_MODEL`, `OPENAI_BASE_URL` | Uses the official OpenAI Chat Completions API with retry logic and token counting. |
| `anthropic` | `ANTHROPIC_API_KEY`, optional `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS` | Integrates with Anthropic Claude via the Messages API with streaming support. |
| `custom` | `CUSTOM_LLM_URL`, optional `CUSTOM_LLM_API_KEY`, `CUSTOM_LLM_MODEL`, `CUSTOM_LLM_HEADERS` | Targets any OpenAI-compatible endpoint by forwarding messages and headers. |

All adapters expose both standard responses and streaming generators. Token usage is estimated with `tiktoken` when available so you can monitor cost across providers.

