FROM python:3.12-slim

LABEL org.opencontainers.image.title="LogSentinel"
LABEL org.opencontainers.image.description="Multi-format log parser and incident tracker"
LABEL org.opencontainers.image.source="https://github.com/Sadhik2607/daily-builds/tree/main/day-03-log-incident-tracker"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY log_incident_tracker/ ./log_incident_tracker/
COPY sample_data/ ./sample_data/

# Non-root user
RUN useradd -m appuser
USER appuser

# Default output directory
RUN mkdir -p /app/output

ENTRYPOINT ["python", "-m", "log_incident_tracker.cli"]
CMD ["--help"]
