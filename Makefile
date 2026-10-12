# Local development stack. `make` or `make help` lists the targets.

# Use the native Docker Engine for this project only: no VM, so far less memory than Docker
# Desktop. This does not change the Docker context for anything else on the laptop.
export DOCKER_CONTEXT := default

COMPOSE := docker compose --env-file .env -f platform/compose.yaml
# Also sees services behind a profile (observability). Used by every target except `up`,
# so `make up` starts only the core stack while `down`, `ps` and `stats` cover everything.
COMPOSE_ALL := $(COMPOSE) --profile observability

.DEFAULT_GOAL := help
.PHONY: help up down ps logs psql redis-cli rpk stats nuke obs-up obs-down otel-smoke

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

# Created only when missing, so existing passwords are never overwritten
# (Postgres keeps the passwords it was first started with).
.env:
	@sed -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$$(tr -dc a-f0-9 </dev/urandom | head -c 32)/" \
	     -e "s/^SERVICE_DB_PASSWORD=.*/SERVICE_DB_PASSWORD=$$(tr -dc a-f0-9 </dev/urandom | head -c 32)/" \
	     .env.example > .env
	@echo "Created .env with random passwords (git-ignored)."

up: .env ## Start Postgres, Redis and Redpanda; waits until all are healthy
	$(COMPOSE) up -d --wait

down: ## Stop all containers, observability included (data is kept)
	$(COMPOSE_ALL) down

ps: ## Show containers and their health
	$(COMPOSE_ALL) ps

logs: ## Follow logs; one service: make logs s=postgres
	$(COMPOSE_ALL) logs -f $(s)

psql: ## psql as the admin user; another database: make psql db=trips
	$(COMPOSE) exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d $(or $(db),postgres)'

redis-cli: ## Open redis-cli
	$(COMPOSE) exec redis redis-cli

rpk: ## Run an rpk command, e.g. make rpk args="topic list"
	$(COMPOSE) exec redpanda rpk $(args)

stats: ## Memory and CPU per container
	docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' $$($(COMPOSE_ALL) ps -q)

nuke: ## Stop the containers and DELETE all their data
	$(COMPOSE_ALL) down -v

obs-up: .env ## Start Grafana and the OTel collector, Prometheus, Loki, Tempo; waits until healthy
	$(COMPOSE_ALL) up -d --wait lgtm
	@echo "Grafana: http://localhost:$$(grep -E '^GRAFANA_PORT=' .env | cut -d= -f2 | grep . || echo 3000)"

obs-down: ## Stop the observability stack (data is kept)
	$(COMPOSE_ALL) down lgtm

otel-smoke: ## Send a test span, metric and log line to the observability stack
	uv run python platform/otel_smoke.py
