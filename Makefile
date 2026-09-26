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
	uv run mypy src

format:
	uv run ruff format .

migrate:
	DATABASE_URL="$(HOST_DATABASE_URL)" uv run alembic upgrade head

seed: migrate
	DATABASE_URL="$(HOST_DATABASE_URL)" uv run python -m src.ingestion.run --sample-days 3

# The targets below are specified by prompt.md § 49 for later phases. They print
# a clear status instead of failing, so `make <target>` is never a broken command
# — see docs/implementation-roadmap.md for when each one gets real content.
train:
	@echo "Not implemented yet — fraud model training lands in Phase 4 (docs/implementation-roadmap.md)."

evaluate:
	@echo "Not implemented yet — python -m evaluation.run lands in Phase 11 (docs/implementation-roadmap.md)."

redteam:
	@echo "Not implemented yet — automated red-team suite lands in Phase 8 (docs/implementation-roadmap.md)."

demo:
	@echo "Not implemented yet — deterministic demo scenarios land in Phase 12 (docs/implementation-roadmap.md)."

docker-up:
	docker compose up -d

docker-down:
	docker compose down
