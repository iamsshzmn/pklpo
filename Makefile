.DEFAULT_GOAL := help
SHELL := /bin/bash

PYTHON ?= python
SRC := src
TESTS := tests

.PHONY: help setup lint typecheck test test-all check format smoke clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv and install deps
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"
	@echo "Activate: source .venv/bin/activate"

lint: ## Run ruff linter and format check
	ruff check $(SRC) $(TESTS)
	ruff format --check $(SRC) $(TESTS)

format: ## Auto-format code
	ruff check --fix $(SRC) $(TESTS)
	ruff format $(SRC) $(TESTS)

typecheck: ## Run mypy
	mypy $(SRC)

test: ## Run fast tests (no slow/integration)
	pytest -m "not slow and not integration" --override-ini addopts="" -q

test-all: ## Run all tests
	pytest --override-ini "addopts=--strict-markers --strict-config -v --tb=short"

smoke: ## CLI smoke check
	$(PYTHON) -m src.cli.main --help

check: lint typecheck test smoke ## Run full validation suite

clean: ## Remove build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
