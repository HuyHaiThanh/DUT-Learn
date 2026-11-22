# Hosted demo image (Hugging Face Docker Space, CPU only).
# Build context = the assembled Space folder (see build_space.ps1), not the repo root.
FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf \
    DUT_DATA_DIR=/app/data \
    DUT_COOKIE_SECURE=true \
    DUT_LLM_PROVIDER=openai \
    DUT_WEB_DIR=/app/web
WORKDIR /app/api
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv
COPY services/api/pyproject.toml services/api/uv.lock ./
# The lock resolves CUDA torch on Linux; install the CPU wheel of the same version
# instead and keep every other package at its locked version.
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/req.txt \
 && TORCH=$(grep -E '^torch==' /tmp/req.txt | cut -d= -f3 | cut -d' ' -f1) \
 && grep -vE '^(torch|triton|nvidia-|cuda-)' /tmp/req.txt > /tmp/req-cpu.txt \
 && uv venv /app/venv \
 && VIRTUAL_ENV=/app/venv uv pip install "torch==${TORCH}" --index-url https://download.pytorch.org/whl/cpu \
 && VIRTUAL_ENV=/app/venv uv pip install --no-deps -r /tmp/req-cpu.txt
ENV PATH=/app/venv/bin:$PATH
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"
COPY services/api/ ./
COPY deploy/hf-space/serve.py ./serve.py
COPY --from=web /web/dist /app/web
COPY data/materials /app/data/materials
RUN useradd -m -u 1000 user && chown -R user /app /opt/hf
USER user
EXPOSE 7860
CMD ["sh", "-c", "for i in 1 2 3 4 5; do alembic upgrade head && break; sleep 3; done; exec uvicorn serve:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips='*'"]
