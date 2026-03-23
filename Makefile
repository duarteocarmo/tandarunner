.PHONY: install format check lint test run migrations clean docker help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	@uv sync

format: ## Format code with ruff
	@uv run ruff check . --fix
	@uv run ruff format .

check: ## Run all checks (lock, ruff, ty, deptry)
	@uv lock --check
	@uv run ruff check .
	@uv run ruff format --check .
	@uv run ty check
	@uv run deptry .

lint: check ## Alias for check

test: ## Run tests
	@uv run pytest --cov=tandarunner --cov-report xml --log-level=WARNING --disable-pytest-warnings

migrations: ## Create new database migrations
	@uv run python manage.py makemigrations

run: ## Run the Django dev server
	@uv run python manage.py migrate --noinput
	@uv run python manage.py collectstatic --noinput
	@uv run python manage.py runserver

clean: ## Delete temporary files
	@rm -rf .ipynb_checkpoints
	@rm -rf **/.ipynb_checkpoints
	@rm -rf .pytest_cache
	@rm -rf **/.pytest_cache
	@rm -rf __pycache__
	@rm -rf **/__pycache__
	@rm -rf build
	@rm -rf dist
	@rm -rf /var/tmp/django_cache

docker: ## Build and run Docker image
	make clean
	docker build -f Dockerfile -t tandarunner .
	docker run -p 8000:8000 tandarunner:latest

.DEFAULT_GOAL := help
