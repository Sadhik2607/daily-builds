.PHONY: install test lint scan-sample scan-all docker-build docker-run clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ --cov=log_incident_tracker --cov-report=term-missing --cov-report=html:htmlcov

lint:
	python -m py_compile log_incident_tracker/*.py && echo "Syntax OK"

scan-apache:
	python -m log_incident_tracker.cli scan sample_data/apache_access.log --format terminal

scan-jsonl:
	python -m log_incident_tracker.cli scan sample_data/app_structured.json --format terminal

scan-python:
	python -m log_incident_tracker.cli scan sample_data/python_app.log --format terminal

scan-nginx:
	python -m log_incident_tracker.cli scan sample_data/nginx_error.log --format terminal

scan-all:
	@echo "=== Apache Access Log ===" && python -m log_incident_tracker.cli scan sample_data/apache_access.log --format terminal
	@echo "=== Structured JSON Log ===" && python -m log_incident_tracker.cli scan sample_data/app_structured.json --format all --output-dir ./output
	@echo "=== Python App Log ===" && python -m log_incident_tracker.cli scan sample_data/python_app.log --format terminal
	@echo "=== NGINX Error Log ===" && python -m log_incident_tracker.cli scan sample_data/nginx_error.log --format terminal

metrics:
	python -m log_incident_tracker.cli metrics sample_data/app_structured.json

docker-build:
	docker build -t logsentinel:latest .

docker-run:
	docker run --rm -v $(PWD)/sample_data:/data -v $(PWD)/output:/reports \
		logsentinel scan /data/app_structured.json --format all --output-dir /reports

clean:
	rm -rf output/ htmlcov/ .pytest_cache/ __pycache__/ log_incident_tracker/__pycache__/ tests/__pycache__/
