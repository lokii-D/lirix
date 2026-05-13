.PHONY: setup lint format typecheck test check clean build

setup:
	@echo "=> Installing development dependencies and pre-commit hooks..."
	python3 -m pip install -e ".[dev]"
	pre-commit install
	@echo "=> Lirix workspace is ready!"

lint:
	python3 tools/harness.py lint

format:
	python3 tools/harness.py format-check

typecheck:
	python3 tools/harness.py typecheck

test:
	python3 -m pytest tests/ -q

check: lint format typecheck

clean:
	rm -rf dist/ build/ *.egg-info/ lirix.egg-info/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +

build: clean
	python3 -m build
