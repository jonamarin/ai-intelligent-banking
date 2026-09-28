.PHONY: install dev test lint typecheck format migrate train evaluate redteam seed demo docker-up docker-down

# Host-mapped Postgres port (see docker-compose.yml and CLAUDE.md § 9) — migrate/seed
# run on the host, not inside a container, so they need the host-mapped port, not
# the .env default (which targets the `db` service's internal Docker hostname).
HOST_DATABASE_URL := postgresql+psycopg://banking:banking@localhost:5433/banking_ai

install:
	uv sync

dev:
	uv run uvicorn src.api.main:app --reload --port 8000

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy src evaluation demo

format:
	uv run ruff format .

migrate:
	DATABASE_URL="$(HOST_DATABASE_URL)" uv run alembic upgrade head

seed: migrate
	DATABASE_URL="$(HOST_DATABASE_URL)" uv run python -m src.ingestion.run --sample-days 3

# The targets below were specified by prompt.md § 49 ahead of the phases that
# implement them; all four now wire to real commands (docs/project-status.md).
# `make` itself was never installed on the machine these were authored on
# (CLAUDE.md § 9) — verified via the underlying `uv`/`docker` commands directly,
# not via `make <target>` itself; treat these as convenience wrapping.
train: migrate
	DATABASE_URL="$(HOST_DATABASE_URL)" uv run python -m src.ml.train

evaluate: migrate
	DATABASE_URL="$(HOST_DATABASE_URL)" uv run python -m evaluation.run

redteam:
	uv run pytest tests/security/ -q

demo:
	uv run python -m demo.run

docker-up:
	docker compose up -d

docker-down:
	docker compose down
