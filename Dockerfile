FROM python:3.11-slim

WORKDIR /app

COPY app/api/requirements.txt /app/api/requirements.txt
COPY entrypoint.sh /entrypoint.sh

# Install Node.js, npm, procps (pgrep/ps used in health checks), PDF processing tools, and execstack
RUN apt-get update && apt-get install -y nodejs npm procps poppler-utils libmagic1 execstack && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --timeout=100 -r /app/api/requirements.txt

# Fix ONNX Runtime executable stack requirement
RUN execstack -c /usr/local/lib/python3.11/site-packages/onnxruntime/capi/onnxruntime_pybind11_state.cpython-311-x86_64-linux-gnu.so

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
