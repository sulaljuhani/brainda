FROM python:3.11-slim

WORKDIR /app

# Install system dependencies first (these rarely change, so cache this layer)
RUN apt-get update && apt-get install -y nodejs npm procps poppler-utils tesseract-ocr libmagic1 binutils && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies (change occasionally)
COPY app/api/requirements.txt /app/api/requirements.txt
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use BuildKit cache mount for faster rebuilds even without Docker layer cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout=100 --upgrade pip \
 && pip install --timeout=100 -r /app/api/requirements.txt

# Verify ONNX Runtime has non-executable stack (security check - without importing)
RUN bash -c 'set -euo pipefail; \
paths=$(python3 -c "import site, glob; [print(p) for d in site.getsitepackages() for p in glob.glob(d + \"/onnxruntime/**/*.so\", recursive=True)]"); \
echo "Discovered ONNX Runtime shared objects:"; echo "$paths"; \
bad=0; \
for so in $paths; do \
  line=$(readelf -lW "$so" | grep GNU_STACK || true); \
  echo "[$so] $line"; \
  if echo "$line" | grep -q " E "; then bad=1; fi; \
done; \
if [ "$bad" -eq 1 ]; then \
  echo "ERROR: At least one ONNX Runtime .so requests an executable stack (GNU_STACK ... E)."; \
  echo "Use a different onnxruntime wheel (or rebuild with -Wl,-z,noexecstack)."; \
  exit 1; \
else \
  echo "✓ All ONNX Runtime .so files have non-executable stack."; \
fi'

# Install frontend dependencies
COPY app/web/package.json /app/web/
RUN --mount=type=cache,target=/root/.npm \
    cd /app/web && npm install
# Pre-download sentence-transformers model so runtime tasks don't spend minutes caching it
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
PY

COPY app/ /app/

ENV PYTHONPATH="/app"
ENV TOKENIZERS_PARALLELISM=false

ENTRYPOINT ["/entrypoint.sh"]
