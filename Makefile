.PHONY: run test lint format check

PYTHON := .venv/bin/python

run:
	$(PYTHON) app.py

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m isort .
	$(PYTHON) -m black .

check: lint test
