FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python sample_data/build_demo_db.py sample_data/demo.sqlite3

ENTRYPOINT ["python", "-m", "transit_pulse.cli"]
CMD ["analyze", "sample_data/demo.sqlite3", "--format", "all", "--output-dir", "/app/reports"]
