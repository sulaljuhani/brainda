FROM python:3.11-slim

WORKDIR /app

COPY app/api/requirements.txt /app/api/requirements.txt
COPY entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir --timeout=100 --upgrade pip \
 && pip install --no-cache-dir --timeout=100 -r /app/api/requirements.txt

# Install Node.js, npm, procps (pgrep/ps used in health checks), PDF processing tools, and binutils (for readelf)
RUN apt-get update && apt-get install -y nodejs npm procps poppler-utils libmagic1 binutils && rm -rf /var/lib/apt/lists/*

# Verify ONNX Runtime has non-executable stack (security check)
RUN python3 -c "import onnxruntime; import pathlib; \
p = pathlib.Path(onnxruntime.__file__).parent; \
so_files = list(p.rglob('*onnxruntime*.so')); \
print(f'Checking {len(so_files)} ONNX Runtime .so files for exec stack...'); \
[print(f'  {f.name}') for f in so_files]" \
 && bash -c 'target=$(python3 -c "import onnxruntime, pathlib; \
p=pathlib.Path(onnxruntime.__file__).parent; \
so_files=list(p.rglob(\"*onnxruntime*.so\")); \
print(str(max(so_files, key=lambda x: len(str(x)))))"); \
echo "Verifying: $target"; \
stack_flags=$(readelf -lW "$target" | grep GNU_STACK); \
echo "$stack_flags"; \
if echo "$stack_flags" | grep -q " E "; then \
  echo "ERROR: ONNX Runtime has executable stack flag!"; exit 1; \
else \
  echo "✓ ONNX Runtime stack is non-executable (secure)"; \
fi'

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
