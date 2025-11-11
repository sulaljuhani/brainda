#!/bin/sh
set -e
set -x

# Ensure multipart support for FastAPI uploads
python - <<'PY' >/dev/null 2>&1 || pip install --no-cache-dir python-multipart
import importlib
importlib.import_module("multipart")
PY

if [ "$SERVICE" = "worker" ]; then
  exec celery -A worker.tasks worker --loglevel=info
elif [ "$SERVICE" = "beat" ]; then
  exec celery -A worker.tasks beat --loglevel=info
else
  exec uvicorn api.main:app --host 0.0.0.0 --port 8000
fi
