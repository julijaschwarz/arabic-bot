# syntax=docker/dockerfile:1

# ---------- builder: все зависимости ставятся в изолированный venv ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# venv, а не системный site-packages: зависимости живут отдельно от питона образа
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip setuptools wheel && pip install .

# ---------- runtime ----------
FROM python:3.12-slim AS runtime

# fonts-hosny-amiri — арабский шрифт для рендера картинок
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-hosny-amiri \
        fonts-dejavu-core \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Переменные живут в рамках окружения контейнера и его venv, а не глобально на хосте
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    DB_PATH=/data/arabic.db

RUN useradd --create-home --uid 1000 arabic \
    && mkdir -p /data && chown -R arabic:arabic /data

USER arabic
WORKDIR /app

VOLUME ["/data"]

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import pathlib,sys,time; p=pathlib.Path('/data/heartbeat'); sys.exit(0 if p.exists() and time.time()-p.stat().st_mtime < 180 else 1)"

CMD ["python", "-m", "arabic_bot"]
