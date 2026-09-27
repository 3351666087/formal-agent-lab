# formal-agent-lab — run these inside the Ubuntu dev VM (scripts/in-vm.sh make <target> from macOS).
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

export UV_PROJECT_ENVIRONMENT ?= $(HOME)/.venvs/formal-agent-lab
export PATH := $(HOME)/.local/bin:$(PATH)
UV_RUN := uv run --frozen
PY := $(UV_RUN) python

COMPOSE_DEV := docker compose -f deploy/compose/services.dev.yaml -p fal-dev

.PHONY: help
help: ## list targets
	@grep -hE '^[a-zA-Z0-9_.-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-22s %s\n",$$1,$$2}'

# ----------------------------------------------------------------- setup
.PHONY: toolchain bootstrap lock
toolchain: ## install pinned toolchain (uv, node, pnpm, helm, temporal cli)
	bash scripts/bootstrap-dev-vm.sh

bootstrap: ## install locked python + node dependencies
	uv sync --frozen --all-packages
	pnpm install --frozen-lockfile

lock: ## re-resolve dependency locks
	uv lock
	pnpm install --lockfile-only

# ----------------------------------------------------------------- contracts
.PHONY: contracts contracts-check
contracts: ## regenerate JSON Schemas, digest and TypeScript types from the Pydantic source
	$(PY) -m formal_lab_contracts.schema_export --out contracts/v1
	pnpm --filter @formal-lab/contracts run generate
	$(PY) -m formal_lab_contracts.docs --out docs/contracts/v1.md

contracts-check: contracts ## fail if generated contracts drift from the committed ones
	git diff --exit-code -- contracts/v1 packages/contracts-ts/src docs/contracts/v1.md

# ----------------------------------------------------------------- quality
.PHONY: lint test test-unit test-integration
lint: ## ruff
	$(UV_RUN) ruff check packages examples tests scripts

test-unit: ## fast tests without external services
	$(UV_RUN) pytest -m "not integration and not llm" -q

test-integration: ## tests against PostgreSQL + Temporal (make services-up first)
	$(UV_RUN) pytest -m integration -q

test: test-unit test-integration ## all tests except real-LLM calls

# ----------------------------------------------------------------- local services
.PHONY: services-up services-down dev-up dev-down dev-status migrate seed
services-up: ## start PostgreSQL, Temporal and the S3 store; apply migrations
	scripts/dev.sh services

services-down: ## stop backing services
	scripts/dev.sh services-down

migrate: ## apply database migrations
	$(PY) -m formal_lab_api.migrate upgrade

seed: ## create the neutral-scheduling demo project
	$(PY) -m formal_lab_api.seed

dev-up: ## start services, API (:8000), worker and web dev server (:5173)
	scripts/dev.sh up

dev-down: ## stop API, worker and web
	scripts/dev.sh down

dev-status: ## show process status
	scripts/dev.sh status

# ----------------------------------------------------------------- build / demo
.PHONY: build web-build demo test-ui test-llm
build: ## build all Python wheels + the web bundle (locked dependencies)
	uv build --all-packages --out-dir out/release/wheels
	pnpm --dir web exec tsc --noEmit -p tsconfig.json
	pnpm --dir web exec vite build

web-build: ## typecheck and build the web app
	pnpm --dir web exec tsc --noEmit -p tsconfig.json
	pnpm --dir web exec vite build

demo: ## run the standalone scheduling example (no server) and print the strategy comparison
	$(PY) -m formal_lab_example_scheduling check
	$(PY) -m formal_lab_example_scheduling compare --seeds 1,2 --out out/demo/comparison.json

test-ui: ## Playwright browser tests of the six web areas (needs services + `playwright install chromium`)
	$(UV_RUN) pytest tests/integration/test_web_ui.py -m "integration and ui" -q

test-llm: ## real-model integration check (needs FAL_LLM_API_KEY)
	$(UV_RUN) pytest tests/integration/test_llm_real.py -m llm -q

# ----------------------------------------------------------------- containers / deployment
COMPOSE := docker compose -f deploy/compose/docker-compose.yaml
.PHONY: images compose-up compose-down compose-smoke helm-lint helm-install-check
images: ## build the api / worker / web OCI images
	FAL_SOURCE_REVISION=$$(git rev-parse HEAD) $(COMPOSE) build

compose-up: ## run the full containerised stack on http://127.0.0.1:8080
	FAL_SOURCE_REVISION=$$(git rev-parse HEAD) $(COMPOSE) up -d --build --wait
	$(COMPOSE) run --rm api python -m formal_lab_api.seed

compose-down: ## stop the containerised stack (keeps volumes)
	$(COMPOSE) down

compose-smoke: ## build, start, run an experiment + matrix through :8080, record evidence, tear down
	scripts/compose-smoke.sh

helm-lint: ## helm lint + template + kubeconform for the chart
	helm lint deploy/helm/formal-agent-lab --strict
	helm template fal deploy/helm/formal-agent-lab | kubeconform -strict -summary -kubernetes-version 1.31.0

helm-install-check: ## install the chart into a throw-away kind cluster and run an experiment through it
	scripts/helm-install-check.sh

# ----------------------------------------------------------------- release / acceptance
.PHONY: release offline-bundle phase1-check handoff
release: ## wheels + web bundle + images → out/release with manifest.json
	uv run --frozen python scripts/release.py

offline-bundle: ## offline package (images, wheels, web, manifest) → out/offline
	uv run --frozen python scripts/offline_bundle.py --verify

phase1-check: ## run every phase-1 acceptance check and write docs/handoff/phase1-checks.json
	uv run --frozen python scripts/phase1_check.py

handoff: ## regenerate docs/handoff/phase1.manifest.json from the repository and check results
	uv run --frozen python scripts/handoff.py

.PHONY: reclaim-disk
reclaim-disk: ## drop Docker build cache / dangling images and return freed blocks to the host (VM disks are sparse)
	# only our own artefacts: the Docker daemon may hold other projects' images — never prune -a / system prune
	docker builder prune -af
	docker image prune -f
	-docker rmi $$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^formal-agent-lab/.+:[0-9a-f]{12}$$') 2>/dev/null
	-docker rmi $$(docker images --format '{{.Repository}}@{{.Digest}}' | grep '^kindest/node') 2>/dev/null
	sudo fstrim -av
