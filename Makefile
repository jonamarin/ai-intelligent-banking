.PHONY: install dev test lint typecheck format train evaluate redteam seed demo docker-up docker-down

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

# The targets below are specified by prompt.md § 49 for later phases. They print
# a clear status instead of failing, so `make <target>` is never a broken command
# — see docs/implementation-roadmap.md for when each one gets real content.
train:
	@echo "Not implemented yet — fraud model training lands in Phase 4 (docs/implementation-roadmap.md)."

evaluate:
	@echo "Not implemented yet — python -m evaluation.run lands in Phase 11 (docs/implementation-roadmap.md)."

redteam:
	@echo "Not implemented yet — automated red-team suite lands in Phase 8 (docs/implementation-roadmap.md)."

seed:
	@echo "Not implemented yet — dataset ingestion lands in Phase 3 (docs/implementation-roadmap.md). Raw files are already at data/raw/ (docs/data-lineage.md)."

demo:
	@echo "Not implemented yet — deterministic demo scenarios land in Phase 12 (docs/implementation-roadmap.md)."

docker-up:
	docker compose up -d

docker-down:
	docker compose down
