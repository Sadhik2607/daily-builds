FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cloudenv/ ./cloudenv/

ENTRYPOINT ["python", "-m", "cloudenv.cli"]
CMD ["--help"]
