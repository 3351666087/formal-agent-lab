# formal-agent-lab — run these inside the Ubuntu dev VM (scripts/in-vm.sh make <target> from macOS).
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

export UV_PROJECT_ENVIRONMENT ?= $(HOME)/.venvs/formal-agent-lab
export PATH := $(HOME)/.local/bin:$(PATH)
UV_RUN := uv run --frozen
# loopback never through an HTTP proxy from the environment (Lima copies the host's proxy into the VM)
comma := ,
export NO_PROXY := $(if $(NO_PROXY),$(NO_PROXY)$(comma))127.0.0.1,localhost,::1
export no_proxy := $(NO_PROXY)
PY := $(UV_RUN) python

COMPOSE_DEV := docker compose -f deploy/compose/services.dev.yaml -p fal-dev

.PHONY: help
help: ## list targets
	@grep -hE '^[a-zA-Z0-9_.-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-22s %s\n",$$1,$$2}'

# ----------------------------------------------------------------- setup
.PHONY: toolchain bootstrap lock
doctor: ## report OS/arch, usable CPU/memory, disk, Docker, ports, toolchain and local profile availability
	python3 scripts/doctor.py

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
contracts: ## regenerate JSON Schemas, digests, TypeScript types and docs (v2 live, v1 frozen) from the Pydantic source
	$(PY) -m formal_lab_contracts.schema_export --out contracts/v2 --v1-out contracts/v1
	pnpm --filter @formal-lab/contracts run generate
	$(PY) -m formal_lab_contracts.docs --out docs/contracts/v2.md --v1-out docs/contracts/v1.md

contracts-check: contracts ## fail if generated contracts drift from the committed ones (untracked output counts as drift)
	git diff --exit-code -- contracts packages/contracts-ts/src docs/contracts
	test -z "$$(git status --porcelain --untracked-files=all -- contracts packages/contracts-ts/src docs/contracts)"

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
orders-up: ## start the local order service example on 127.0.0.1:8765 (project "dev", data in var/.fal-orders)
	$(PY) -m formal_lab_example_orders.lifecycle up --project dev

orders-down: ## stop it (data kept; `ARGS=--purge` removes it)
	$(PY) -m formal_lab_example_orders.lifecycle down --project dev $(ARGS)

orders-status: ## show the order service manifest and health
	$(PY) -m formal_lab_example_orders.lifecycle status --project dev

orders-e2e: ## order service end to end from an empty work dir (process + compose), real logs in docs/execution/evidence/phase2/orders
	rm -rf var/orders-e2e-process var/orders-e2e-compose
	$(PY) -m formal_lab_example_orders.e2e --workdir var/orders-e2e-process --mode process --log docs/execution/evidence/phase2/orders/e2e-process.log --summary docs/execution/evidence/phase2/orders/e2e-process.json
	$(PY) -m formal_lab_example_orders.e2e --workdir var/orders-e2e-compose --mode compose --project e2ecompose --log docs/execution/evidence/phase2/orders/e2e-compose.log --summary docs/execution/evidence/phase2/orders/e2e-compose.json

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

.PHONY: phase3-check checks design-check
phase3-check: ## phase-3A local checks (engine: scripts/check_runner.py) → docs/execution/evidence/phase3/checks/ (ARGS="--group g" / "--only id" / "--out dir")
	$(UV_RUN) python scripts/phase3_check.py $(ARGS)

design-check: ## design sources in sync: tokens.css ← design/tokens.json, demo / architecture SVG ← design/animation
	python3 scripts/design_tokens.py --check && python3 scripts/render_demo.py svg && git diff --exit-code -- docs/assets/demo.svg docs/assets/demo-cover.svg docs/assets/demo.html docs/assets/architecture.svg

checks: ## any suite on the check engine: make checks SUITE=phase2 ARGS="--list"
	$(UV_RUN) python scripts/check_runner.py --suite $(or $(SUITE),phase3) $(ARGS)

.PHONY: phase2-check handoff-phase2 prism-games-check disk-guard
phase2-check: ## phase-2 local acceptance: all check groups → docs/handoff/phase2-checks.json (ARGS="--group g" / "--only id")
	$(PY) scripts/phase2_check.py $(ARGS)

handoff-phase2: ## regenerate docs/handoff/phase2.manifest.json and the tables in phase2.md from the check results
	$(PY) scripts/handoff_phase2.py

prism-games-check: ## optional track: PRISM-games queries verified in-model (needs a local PRISM-games, see docs/local-development.md)
	$(PY) scripts/prism_games_check.py

disk-guard: ## report free space on the host disk (through the shared repo) and /var/lib/docker; return freed VM blocks
	python3 scripts/disk_guard.py --need 0 --trim

.PHONY: reclaim-disk
reclaim-disk: ## remove this project's dangling / commit-tagged images and return freed blocks to the host (VM disks are sparse)
	# the Docker daemon is shared with other projects: only images labelled with this repository are removed; the
	# global build cache and shared images (e.g. kindest/node) are left alone — never prune -a / system prune
	docker image prune -f --filter label=org.opencontainers.image.source=https://github.com/3351666087/formal-agent-lab
	-docker rmi $$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^formal-agent-lab/.+:(p1-)?[0-9a-f]{7,12}$$') 2>/dev/null
	python3 scripts/disk_guard.py --need 0 --trim
