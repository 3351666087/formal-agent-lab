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

contracts-check: contracts ## fail if generated contracts drift from the committed ones
	git diff --exit-code -- contracts/v1 packages/contracts-ts/src

# ----------------------------------------------------------------- quality
.PHONY: lint test test-unit test-integration
lint: ## ruff
	$(UV_RUN) ruff check packages examples tests scripts

test-unit: ## fast tests without external services
	$(UV_RUN) pytest -m "not integration and not llm" -q

test-integration: ## tests against PostgreSQL + Temporal (make services-up first)
	$(UV_RUN) pytest -m integration -q

test: test-unit test-integration ## all tests except real-LLM calls
