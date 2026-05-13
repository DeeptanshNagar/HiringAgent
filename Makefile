.PHONY: help install dev lint format type-check test test-cov clean docker-build docker-run run api

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -r requirements.txt

dev: install ## Install dev dependencies (linting, testing)
	pip install ruff mypy pip-audit

lint: ## Run linter (ruff)
	ruff check .

format: ## Auto-format code (ruff)
	ruff format .

type-check: ## Run type checker (mypy)
	mypy config.py agent/exceptions.py agent/llm_factory.py --ignore-missing-imports

test: ## Run all tests
	pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage
	pytest tests/ -v --cov=agent --cov=security --cov-report=term-missing

clean: ## Remove generated files
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docker-build: ## Build Docker image
	docker build -t hr-shortlisting-agent .

docker-run: ## Run via Docker Compose
	docker-compose up -d

run: ## Run Streamlit app locally
	streamlit run app.py

api: ## Run FastAPI server locally
	uvicorn api:app --host 0.0.0.0 --port 8000 --reload
