.PHONY: help install backend-install frontend-install lint test typecheck build dev-backend dev-frontend up down diagrams

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-18s %s\n", $$1, $$2}'

install: backend-install frontend-install ## Install backend + frontend deps

backend-install: ## uv sync backend
	cd backend && uv sync

frontend-install: ## npm ci frontend
	cd frontend && npm ci

lint: ## Ruff (lint + format check) and oxlint
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

test: ## Backend tests
	cd backend && uv run pytest

typecheck: ## Frontend typecheck
	cd frontend && npm run typecheck

build: ## Frontend production build
	cd frontend && npm run build

dev-backend: ## Run FastAPI with reload on :8000
	cd backend && uv run uvicorn jewel.api.app:app --reload

dev-frontend: ## Run Vite dev server on :5173
	cd frontend && npm run dev

up: ## docker compose up (neo4j, postgres, backend, frontend)
	docker compose -f infra/docker-compose.yml --env-file .env up --build

down: ## docker compose down
	docker compose -f infra/docker-compose.yml down

diagrams: ## Extract Mermaid blocks from docs/architecture.md and render PNGs (needs Node + Chrome)
	python3 docs/diagrams/extract.py
	for f in docs/diagrams/*.mmd; do npx -y -p @mermaid-js/mermaid-cli mmdc -i $$f -o $${f%.mmd}.png -p docs/diagrams/puppeteer.json -b white -s 2 || exit 1; done
