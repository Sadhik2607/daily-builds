# ── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install dependencies into a dedicated prefix so we can copy cleanly
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="Sadhik Ahamed <epictechtales@gmail.com>" \
      org.opencontainers.image.title="SecretSentinel" \
      org.opencontainers.image.description="Enterprise secrets scanner — DevSecOps grade" \
      org.opencontainers.image.source="https://github.com/Sadhik2607/daily-builds" \
      org.opencontainers.image.version="1.0.0"

# Non-root user for security
RUN addgroup --gid 1001 scanner && \
    adduser  --uid 1001 --gid 1001 --disabled-password --no-create-home scanner

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=scanner:scanner scanner/ ./scanner/
COPY --chown=scanner:scanner main.py  ./main.py

# Mount point for the repo to scan
VOLUME ["/scan-target"]

USER scanner

ENTRYPOINT ["python", "main.py", "/scan-target"]
CMD ["--format", "terminal"]

# Usage:
#   docker build -t secretsentinel .
#   docker run --rm -v $(pwd):/scan-target secretsentinel
#   docker run --rm -v $(pwd):/scan-target secretsentinel --format sarif -o /scan-target/results.sarif
