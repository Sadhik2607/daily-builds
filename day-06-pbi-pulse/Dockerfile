FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pbi_pulse/ pbi_pulse/
COPY sample_data/ sample_data/

ENTRYPOINT ["python", "-m", "pbi_pulse.cli"]
CMD ["scan", "--demo", "--out", "/app/reports"]
