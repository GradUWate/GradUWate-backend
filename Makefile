
.PHONY: install dev run test lint type fmt export-reqs

install:
	poetry install --no-root

dev:
	poetry install --no-root --with dev

run:
	poetry run uvicorn app.main:app --reload --port 8000

test:
	poetry run pytest -q

lint:
	poetry run ruff check .

fmt:
	poetry run ruff check . --fix

type:
	poetry run mypy app

# Export pinned requirements if you want a requirements.txt for Docker/Heroku/etc.
export-reqs:
	poetry export -f requirements.txt --output requirements.txt --without-hashes
	poetry export -f requirements.txt --output requirements-dev.txt --with dev --without-hashes
