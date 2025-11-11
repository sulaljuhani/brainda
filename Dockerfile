FROM python:3.11-slim

WORKDIR /app

COPY app/api/requirements.txt /app/api/requirements.txt
COPY entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir --timeout=100 -r /app/api/requirements.txt

# Install Node.js, npm, and procps (pgrep/ps used in health checks)
RUN apt-get update && apt-get install -y nodejs npm procps && rm -rf /var/lib/apt/lists/*

# Install frontend dependencies
COPY app/web/package.json /app/web/
RUN cd /app/web && npm install
# Pre-download sentence-transformers model so runtime tasks don't spend minutes caching it
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
PY

COPY app/ /app/

ENV PYTHONPATH="/app"
ENV TOKENIZERS_PARALLELISM=false

ENTRYPOINT ["/entrypoint.sh"]
