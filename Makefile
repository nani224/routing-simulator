.PHONY: all dev test check bench clean install lint format typecheck

VENV = .venv
ifeq ($(OS),Windows_NT)
	PYTHON = $(VENV)/Scripts/python.exe
	PIP = $(VENV)/Scripts/pip.exe
	RUFF = $(VENV)/Scripts/ruff.exe
	MYPY = $(VENV)/Scripts/mypy.exe
	PYTEST = $(VENV)/Scripts/pytest.exe
else
	PYTHON = $(VENV)/bin/python
	PIP = $(VENV)/bin/pip
	RUFF = $(VENV)/bin/ruff
	MYPY = $(VENV)/bin/mypy
	PYTEST = $(VENV)/bin/pytest
endif

all: check

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -e ".[dev]"
	cd frontend && npm install

dev:
	$(PYTHON) -m routelab.api.server & cd frontend && npm run dev

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

typecheck:
	$(MYPY) --strict backend/routelab

test:
	$(PYTEST) -v --cov=routelab --cov-report=term-missing --cov-report=html:docs/results/coverage_html backend/tests/

check: lint typecheck test
	cd frontend && npm run build

bench:
	$(PYTHON) -m pytest backend/tests/bench/ -v -s

clean:
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
