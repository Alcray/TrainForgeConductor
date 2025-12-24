.PHONY: help install install-dev run test clean docker-build docker-run docker-stop

help:
	@echo "TrainForgeConductor - Available commands:"
	@echo ""
	@echo "  make install      Install production dependencies"
	@echo "  make install-dev  Install with dev dependencies"
	@echo "  make run          Run the conductor server"
	@echo "  make test         Run tests (pytest)"
	@echo "  make test-quick   Run quick tests"
	@echo "  make clean        Remove cache and build files"
	@echo ""
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-run   Run in Docker"
	@echo "  make docker-stop  Stop Docker container"
	@echo ""
	@echo "First time setup:"
	@echo "  1. python -m venv .venv"
	@echo "  2. source .venv/bin/activate"
	@echo "  3. make install-dev"
	@echo "  4. cp config/config.example.yaml config/config.yaml"
	@echo "  5. Edit config/config.yaml with your API keys"
	@echo "  6. make run"

install:
	pip install .

install-dev:
	pip install -e ".[dev]"

run:
	trainforge-conductor

run-dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

test-quick:
	python tests/test_conductor.py

clean:
	rm -rf __pycache__ .pytest_cache .eggs *.egg-info build dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

docker-build:
	docker build -t trainforge-conductor .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f
