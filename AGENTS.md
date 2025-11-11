# Repository Guidelines

## Project Structure & Module Organization
- `app/api/` FastAPI services, routers, models, and Celery tasks. Keep HTTP handlers thin; push logic into `services/` modules.
- `app/web/` Next.js client components such as `DocumentUpload.tsx` and chat UI pieces.
- `migrations/` Incremental SQL files (e.g., `003_add_documents.sql`) applied through Postgres container.
- `tests/` Shell scripts and fixtures; Stage 3 adds `tests/stage3-validation.sh` plus documents under `tests/fixtures/`.
- `devloper_notes/` Long-form specs (`README-FINAL-1.md`, `ROADMAP-FINAL-1.md`, `PATCHES-TO-APPLY.md`). Read Stage 3 before touching ingestion code.

## Build, Test, and Development Commands
- `docker compose up -d` — boots API, worker, Postgres, Redis, Qdrant, Ollama, and Unstructured.
- `docker compose exec vib-api alembic upgrade head` — run DB migrations if Alembic is used; otherwise `docker exec vib-postgres psql -U postgres -d vib -f migrations/<file>.sql`.
- `npm install && npm run dev --prefix app/web` — launch the web client with hot reload.
- `tests/stage3-validation.sh` — full Stage 3 smoke test (ingestion, RAG, dedupe, metrics). Requires pandoc for fixture PDFs.

## Coding Style & Naming Conventions
- Python: 4-space indent, type hints everywhere, docstrings for public services. Prefer `async` functions that wrap DB calls via `asyncpg` or similar. Run `ruff` & `black` if configured.
- TypeScript/React: functional components, hooks-first, CSS via Tailwind utility classes. Use PascalCase for components, camelCase for props/state.
- SQL files: snake_case table/column names, comments before complex indexes or constraints.

## Testing Guidelines
- Favor black-box scripts in `tests/`. Name new scripts `stage<N>-*.sh` and keep them idempotent.
- For API-level tests, hit the running containers with `curl` and assert via `jq`.
- Add synthetic documents in `tests/fixtures/` to cover parsing edge cases (OCR, tables, long text). Clean temporary files in scripts.

## Commit & Pull Request Guidelines
- Commits: present-tense, concise summary (`add document ingestion jobs`, `fix celery retry logic`). Group related backend & frontend changes together when possible.
- PRs: include checklist of touched Stage acceptance criteria, describe manual validation steps (commands + screenshots for UI). Link relevant roadmap items or issues and note any follow-up work (e.g., OCR backlog).

## Security & Configuration Tips
- Never commit `.env`; copy `.env.example` and override secrets locally. API auth uses bearer tokens from the `users` table.
- Uploaded binaries land under `/app/uploads/<user>/<sha>_filename`; ensure perms stay 600 and garbage-collect on document deletion.
- When handling user data, log request IDs + document IDs but redact file contents.
