# syntax=docker/dockerfile:1.7
# Builds the UI and the wheel, then runs a thin host that installs the wheel
# (the same satellite-library path a real host application would use).

FROM node:20-bookworm-slim AS ui
WORKDIR /src/ui
RUN corepack enable
COPY ui/package.json ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY ui/ ./
RUN pnpm run build

FROM python:3.12-slim-trixie AS wheel
WORKDIR /src
RUN pip install --no-cache-dir 'poetry>=2,<3'
COPY pyproject.toml poetry.lock README.md ./
COPY src ./src
RUN rm -rf src/gitpulse/static
COPY --from=ui /src/ui/dist ./src/gitpulse/static
RUN poetry build --format wheel

FROM python:3.12-slim-trixie
# git >= 2.45 is required for GIT_NO_LAZY_FETCH (trixie ships 2.47).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 gitpulse \
    && mkdir -p /data \
    && chown gitpulse:gitpulse /data
WORKDIR /app
COPY --from=wheel /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
COPY deploy/host/app.py ./app.py

ENV GITPULSE_REMOTE_ENABLED=true \
    GITPULSE_DATA_DIR=/data \
    PYTHONUNBUFFERED=1 \
    PORT=8000
USER gitpulse
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=4)"
# One worker: the repository registry and the analytics cache live in process memory.
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
