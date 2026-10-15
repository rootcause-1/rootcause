SHELL := bash
PY ?= uv run python
COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env
REPLAY_COMPOSE := docker compose -f infra/docker-compose.replay.yml
N ?= 15
SCENARIO ?= paymentFailure

.PHONY: demo-up demo-down up down seed lint test scenario-test chaos record replay-up ui queries-doc

demo-up:            ## OpenTelemetry Demo in agentic mode with our collector override
	bash scripts/setup_demo.sh

demo-down:
	cd $${DEMO_REPO_PATH:-../opentelemetry-demo} && make stop

up:                 ## our stack on the demo's network
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

seed:               ## indexes + config/seed.yaml into the current graph
	$(COMPOSE) exec rootcause-api python -m rootcause.graph.schema --seed

lint:
	uv run ruff check backend tests scripts

test:               ## unit + graph tests (graph tests skip without Docker)
	uv run pytest tests/unit tests/graph -q

scenario-test:      ## golden replay tests
	uv run pytest tests/scenarios -q

chaos:              ## blind chaos runs + scorecard (needs `make up` + demo)
	$(PY) -m rootcause.chaos.runner --n $(N)

record:             ## record one scenario: 3 min healthy, break, 3 min broken, fix, 2 min recovery
	$(PY) scripts/record_scenario.py --scenario $(SCENARIO)

replay-up:          ## public deployment stack locally (no demo needed)
	$(REPLAY_COMPOSE) up -d --build

ui:
	cd frontend && npm install && npm run dev

queries-doc:        ## regenerate docs/QUERIES.md from the .cypher headers
	$(PY) scripts/gen_queries_doc.py
