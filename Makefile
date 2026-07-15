# LedgerPulse developer commands.
# On Windows, run these from Git Bash, WSL, or use the raw docker commands shown.
COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml

.PHONY: help dev up down logs ps build seed demo-reset migrate revision test-api test-web e2e golden fmt

help:
	@echo "LedgerPulse make targets:"
	@echo "  make dev          - build + start the full stack (api runs migrations + seed)"
	@echo "  make down         - stop the stack"
	@echo "  make logs         - tail all logs"
	@echo "  make migrate      - run alembic upgrade head inside the api container"
	@echo "  make revision m=  - create an alembic autogenerate revision"
	@echo "  make seed         - (re)seed master data + demo invoices"
	@echo "  make demo-reset   - deterministic reset: fresh DB + reseed 8 demo invoices"
	@echo "  make test-api     - run pytest (unit + integration) in the api container"
	@echo "  make e2e          - run Playwright end-to-end tests"
	@echo "  make golden       - run the model golden-eval suite (mock provider)"

dev:
	@test -f .env || cp .env.example .env
	$(COMPOSE) up --build -d
	@echo "Web: http://localhost:3000   API: http://localhost:8000/docs   Mailpit: http://localhost:8025   MinIO: http://localhost:9001"

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

migrate:
	$(COMPOSE) exec api alembic upgrade head

revision:
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

seed:
	$(COMPOSE) exec api python -m app.seed

demo-reset:
	$(COMPOSE) exec api python -m app.demo_reset

test-api:
	$(COMPOSE) exec api pytest -q

test-web:
	$(COMPOSE) exec web pnpm --filter @ledgerpulse/web test

e2e:
	$(COMPOSE) exec web pnpm --filter @ledgerpulse/web exec playwright test

golden:
	$(COMPOSE) exec api pytest -q tests/golden

fmt:
	$(COMPOSE) exec api ruff format .
