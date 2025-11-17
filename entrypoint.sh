#!/bin/sh
set -e
set -x

# Ensure multipart support for FastAPI uploads
python - <<'PY' >/dev/null 2>&1 || pip install --no-cache-dir python-multipart
import importlib
importlib.import_module("multipart")
PY

# Graceful shutdown handler
shutdown() {
  echo "Received shutdown signal, gracefully stopping..."
  # Send SIGTERM to child process
  if [ -n "$child_pid" ]; then
    kill -TERM "$child_pid" 2>/dev/null || true
    # Wait for process to finish (max 30 seconds)
    wait "$child_pid" || true
  fi
  echo "Shutdown complete"
  exit 0
}

# Trap SIGTERM and SIGINT for graceful shutdown
trap shutdown TERM INT

if [ "$SERVICE" = "worker" ]; then
  celery -A worker.tasks worker --loglevel=info &
  child_pid=$!
elif [ "$SERVICE" = "beat" ]; then
  celery -A worker.tasks beat --loglevel=info &
  child_pid=$!
else
  uvicorn api.main:app --host 0.0.0.0 --port 8000 &
  child_pid=$!
fi

# Wait for child process
wait "$child_pid"
