# Brainda - Personal Knowledge Management System

Brainda is a personal knowledge management system that combines note-taking, document ingestion, semantic search, and intelligent reminders. It features RAG (Retrieval Augmented Generation) capabilities powered by multiple LLM providers for answering questions based on your stored knowledge.

## Features

- **Note Management**: Create, update, and organize markdown notes with tags and semantic search
- **Document Ingestion**: Upload and process documents (PDF, text, etc.) with automatic parsing and embedding
- **Semantic Search**: Vector-based search across notes and documents using sentence transformers
- **RAG Chat Interface**: Chat with your knowledge base using Ollama, OpenAI, Anthropic, or custom LLM providers
- **OpenMemory Integration**: Long-term conversational memory with multi-sector semantic recall
- **Modern Web UI**: React-based interface with dark mode, responsive navigation, and streaming chat
- **Smart Reminders**: Schedule reminders with RRULE support and calendar integration
- **Calendar Scheduling**: Create recurring events, weekly calendar view, and Google Calendar sync
- **Push Notifications**: Web push notifications for reminders and updates
- **Multi-User Authentication**: WebAuthn passkeys, session tokens, and TOTP backup codes
- **Metrics & Monitoring**: Prometheus metrics for system health and performance SLOs
- **Mobile App**: React Native (Expo) mobile application for iOS and Android

## Architecture Overview

Brainda uses a microservices architecture with the following key components:

| Component | Purpose | Technology |
| --- | --- | --- |
| **API Server** | REST API and WebSocket endpoints | FastAPI with async/await |
| **Worker** | Background task processing | Celery with Redis broker |
| **Beat Scheduler** | Periodic task scheduling | Celery Beat with APScheduler |
| **PostgreSQL** | Primary data store | PostgreSQL 15 with asyncpg |
| **Redis** | Message broker and cache | Redis 7 |
| **Qdrant** | Vector database | Qdrant for semantic search |
| **Web Frontend** | User interface | React 18 + TypeScript + Vite |
| **Mobile App** | iOS/Android client | React Native (Expo) |

### Key Implementation Highlights

- **Chat-first Interface**: React-based chat UI with streaming responses, tool-call visualization, and conversation history
- **Multi-User Auth**: WebAuthn passkeys with TOTP backup codes and session-based authentication
- **Smart Reminders**: RRULE-aware reminders with calendar integration and deduplication
- **Semantic Search**: Unified vector search across notes and documents using `sentence-transformers/all-MiniLM-L6-v2`
- **Document Pipeline**: SHA-256 deduplication, background embedding jobs, and automatic content extraction
- **Push Notifications**: Multi-platform support (Web Push, FCM, APNs) with TTL and collapse keys
- **Observability**: Prometheus metrics for SLOs, request latency, and business KPIs

## Quick Start

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- At least 4GB RAM available for Docker
- Git

## Installation & Setup

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

**For Development** (recommended for active development with hot reload):

```bash
# Start all services including frontend with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Access:
- Frontend: http://localhost:3000 (Vite dev server with hot reload)
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

**For Production** (single optimized endpoint):

```bash
# Build and start with frontend served from FastAPI
docker compose -f docker-compose.prod.yml up -d --build
```

Access everything at: http://localhost:8000

See [DOCKER_SETUP.md](./DOCKER_SETUP.md) for comprehensive Docker configuration guide.

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
docker compose exec brainda-postgres \
  psql -U vib -d vib -f migrations/006_add_multi_user_auth.sql
```

Repeat this command on each environment when you deploy Stage 8.

## Usage

### Access the Application

- **API Base URL**: http://localhost:8000
- **Health Check**: http://localhost:8000/api/v1/health
- **Metrics**: http://localhost:8000/api/v1/metrics
- **API Docs**: http://localhost:8000/docs

### Modern Web UI

The frontend is built with React 18 + TypeScript and located in `app/web/src/`:
- **Chat Interface**: Streaming chat with conversation history and tool-call visualization
- **Notes Management**: Create, edit, and organize markdown notes with tags
- **Document Upload**: Drag-and-drop document upload with processing status
- **Calendar View**: Weekly calendar with event creation and reminder linking
- **Settings**: API configuration, LLM provider selection, and authentication management
- **Responsive Design**: Mobile-first design with dark mode support

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

Brainda can synchronise calendar events with Google Calendar once you register an OAuth2 client and provide credentials.

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

The web interface includes a dedicated calendar view, and the mobile app (`brainda-mobile/`) provides native calendar access on iOS and Android.

## Development

### Running in Development Mode

**Recommended: Docker Development Mode**

```bash
# Start all services with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f orchestrator frontend

# Restart specific service after changes
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart worker
```

**Alternative: Manual Mode** (for advanced debugging)

```bash
# Start infrastructure only
docker compose up -d postgres redis qdrant

# Run API server locally (terminal 1)
cd app
export PYTHONPATH=$(pwd)
export DATABASE_URL="postgresql://vib:<password>@localhost:5434/vib"
export REDIS_URL="redis://localhost:6379/0"
export QDRANT_URL="http://localhost:6333"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker (terminal 2)
celery -A worker.tasks worker --loglevel=info

# Run Celery beat (terminal 3)
celery -A worker.tasks beat --loglevel=info

# Run web frontend (terminal 4)
cd app/web
npm install
npm run dev
```

See [DEVELOPMENT.md](./DEVELOPMENT.md) for more details.

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

Execute the comprehensive integration test suite:

```bash
# Run all 8 stages of tests
./tests/stage_runner.sh --all --verbose

# Run specific stage
./tests/stage_runner.sh --stage 0 --verbose  # Health and metrics
./tests/stage_runner.sh --stage 1 --verbose  # Notes + vector search
./tests/stage_runner.sh --stage 2 --verbose  # Reminders + scheduler
./tests/stage_runner.sh --stage 3 --verbose  # Documents + RAG
./tests/stage_runner.sh --stage 8 --verbose  # Multi-user auth
```

Available test stages (Stage 0-8):
- **Stage 0**: Health checks and Prometheus metrics
- **Stage 1**: Notes CRUD and vector search
- **Stage 2**: Reminders and scheduler
- **Stage 3**: Document ingestion and RAG
- **Stage 4**: Metrics validation
- **Stage 5**: Idempotency
- **Stage 6**: Calendar events with RRULE
- **Stage 7**: Google Calendar sync
- **Stage 8**: Multi-user authentication (passkeys + TOTP)

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

Database schema is managed through SQL migration files in the `migrations/` directory. Migrations are applied automatically on startup via the FastAPI lifespan handler. For manual migration:

```bash
docker exec brainda-postgres psql -U vib -d vib -f /app/migrations/your_migration.sql
```

Current migrations:
- 001: Core tables (notes, documents, reminders)
- 002: Deduplication indexes
- 003: Document ingestion improvements
- 004: Additional features
- 005: Calendar events and notes constraints
- 006: Multi-user authentication (passkeys, TOTP, sessions)

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
│   │   ├── adapters/          # External service adapters (LLM, OpenMemory, Google)
│   │   ├── models/            # Pydantic request/response models
│   │   ├── routers/           # API route handlers
│   │   ├── services/          # Business logic layer
│   │   ├── middleware/        # Custom middleware (metrics, idempotency, auth)
│   │   └── main.py            # Application entry point
│   ├── common/                # Shared utilities and database connections
│   ├── web/                   # React frontend
│   │   ├── src/               # Source code
│   │   │   ├── components/   # React components (auth, chat, calendar, etc.)
│   │   │   ├── pages/        # Page-level components
│   │   │   ├── hooks/        # Custom React hooks
│   │   │   └── layouts/      # Layout wrappers
│   │   └── package.json      # Frontend dependencies
│   └── worker/                # Celery tasks and scheduler
├── brainda-mobile/            # React Native mobile app (Expo)
├── migrations/                # SQL migration files
├── tests/                     # Integration test suite (Stage 0-8)
├── scripts/                   # Utility scripts
├── docs/                      # Additional documentation
├── vault/                     # Note storage (markdown files)
├── uploads/                   # Uploaded document storage
├── docker-compose.yml         # Base Docker services
├── docker-compose.dev.yml     # Development overlay (hot reload)
├── docker-compose.prod.yml    # Production configuration
├── Dockerfile.dev             # Development Dockerfile
├── Dockerfile.prod            # Production multi-stage build
├── CLAUDE.md                  # Claude Code instructions
├── DOCKER_SETUP.md            # Comprehensive Docker guide
└── README.md                  # This file
```

## Security Considerations

- **API Tokens**: Store API tokens securely, never commit to version control
- **Environment Files**: Keep `.env` files out of version control
- **Network Exposure**: By default, services are exposed on localhost only
- **Production Deployment**: Update CORS settings, use HTTPS, implement proper authentication
- **File Uploads**: Uploaded files are stored with restricted permissions (600)
- **Database**: Use strong passwords and restrict network access in production

## Documentation

- **[CLAUDE.md](./CLAUDE.md)** - Comprehensive guide for Claude Code development
- **[DOCKER_SETUP.md](./DOCKER_SETUP.md)** - Docker configuration modes and best practices
- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - Development workflow and guidelines
- **[PRODUCTION_READY.md](./PRODUCTION_READY.md)** - Production deployment checklist
- **[Agents.md](./Agents.md)** - Development guidelines and coding standards
- **[docs/](./docs/)** - Additional technical documentation

## Recent Cleanup (2025-11-17)

The codebase has been cleaned up with the following improvements:
- Moved 17 test log files to `.review_for_deletion/` for review
- Removed redundant documentation (6 analysis files moved to review)
- Consolidated legacy frontend components (9 files moved from `app/web/components/` to review)
- Removed temporary development files
- Updated README to reflect current architecture
- See `.review_for_deletion/CLEANUP_SUMMARY.md` for details on what was moved

## Contributing

See [Agents.md](./Agents.md) for development guidelines, coding standards, and contribution workflow.

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

