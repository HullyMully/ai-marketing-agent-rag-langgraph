VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip

.DEFAULT_GOAL := help

.PHONY: help setup install install-dev run test lint format typecheck docs check pre-commit

help: ## Show the available development commands
	@awk 'BEGIN {FS = ":.*## "; printf "Available commands:\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(PYTHON):
	python3 -m venv $(VENV)

setup: $(PYTHON) ## Create a virtualenv and install development dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

install: $(PYTHON) ## Install runtime dependencies
	$(PIP) install -r requirements.txt

install-dev: $(PYTHON) ## Install runtime and development dependencies
	$(PIP) install -r requirements-dev.txt

run: ## Start the local FastAPI development server
	$(PYTHON) -m uvicorn app.main:app --reload

test: ## Run the automated test suite
	$(PYTHON) -m pytest

lint: ## Check Python code with Ruff
	$(PYTHON) -m ruff check .

format: ## Format Python code with Ruff
	$(PYTHON) -m ruff format .

typecheck: ## Check application types with mypy
	$(PYTHON) -m mypy app bot scripts

docs: ## Validate bilingual docs and committed demo assets
	$(PYTHON) scripts/check_docs_links.py
	$(PYTHON) scripts/check_demo_assets.py

check: lint typecheck test docs ## Run the same quality checks used in CI

pre-commit: ## Run all pre-commit hooks against the repository
	$(PYTHON) -m pre_commit run --all-files
