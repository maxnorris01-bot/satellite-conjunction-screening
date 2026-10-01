.PHONY: install lint format typecheck test screen publish-local fly-build fly-machine-create fly-update eval-fast eval-fast-live eval-standard eval-nightly
 
install:
	uv sync
 
lint:
	uv run ruff check .
	uv run ruff format --check .
 
format:
	uv run ruff check --fix .
	uv run ruff format .
 
typecheck:
	uv run mypy
 
test:
	uv run pytest

# Run the conjunction screening pipeline (zero LLM calls). Scope/window/threshold come from
# config/screening.yaml; pass overrides with ARGS, e.g. make screen ARGS="--window-hours 48".
# CelesTrak responses are cached for 2h in cache/, so re-running within that window is free.
screen:
	uv run python -m app.cli $(ARGS)
 
# Dry run of the scheduled job (ADR 0009): same pipeline and objects as the Fly run, written to
# runs/publish/ instead of the bucket. Reuses the normal CelesTrak cache, so it's free to repeat.
publish-local:
	uv run python -m app.publish --local-dir runs/publish --cache-dir cache/celestrak

# Fly.io (ADR 0009). Requires flyctl and `fly auth login`. One-time setup is in the README's
# "Daily run" section. FLY_IMAGE_LABEL defaults to the current commit.
FLY_APP ?= satellite-conjunction-screening
FLY_IMAGE_LABEL ?= $(shell git rev-parse --short HEAD)
FLY_IMAGE = registry.fly.io/$(FLY_APP):$(FLY_IMAGE_LABEL)
# --restart no: a failed day leaves yesterday's report in place instead of retrying against CelesTrak.
# --region is valid on `fly machine run` (Machine creation) but not on `fly machine update`
# (a Machine's region is fixed at creation), so it's kept separate from the shared flags below.
FLY_MACHINE_FLAGS = --schedule daily --restart no --vm-memory 1024
FLY_REGION = sjc

fly-build:
	fly deploy --build-only --push --image-label $(FLY_IMAGE_LABEL) -a $(FLY_APP)

fly-machine-create:
	fly machine run $(FLY_IMAGE) $(FLY_MACHINE_FLAGS) --region $(FLY_REGION) -a $(FLY_APP)

# Point the existing scheduled Machine at a newly built image: make fly-update FLY_MACHINE_ID=<id>
fly-update:
	@test -n "$(FLY_MACHINE_ID)" || (echo "set FLY_MACHINE_ID (see: fly machine list -a $(FLY_APP))"; exit 1)
	fly machine update $(FLY_MACHINE_ID) --image $(FLY_IMAGE) $(FLY_MACHINE_FLAGS) -a $(FLY_APP) --yes

# Screening evals (evals/README.md): the real pipeline on frozen synthetic scenarios, checked against
# a brute-force oracle, plus named encounters from the frozen real-data snapshot. No network, no LLM
# calls, $0. APP_LLM_MODE is still forced to mock so that a future LLM step can't make a "fast" run
# silently cost money.
eval-fast:
	APP_LLM_MODE=mock APP_TRACING_DISABLED=1 uv run python -m evals.run --tier fast

# The pipeline makes no LLM calls, so there's no live variant to run: this target says so and runs
# the same free suite. Give it a real live mode if an LLM step (e.g. report summaries) is ever added.
eval-fast-live:
	@echo "No LLM calls in this pipeline: eval-fast-live runs the same free suite as eval-fast."
	APP_LLM_MODE=mock APP_TRACING_DISABLED=1 uv run python -m evals.run --tier fast

# Same suite at larger tiers (all cases fit in fast today). Mode is forced to mock for the same
# reason as eval-fast.
eval-standard:
	APP_LLM_MODE=mock APP_TRACING_DISABLED=1 uv run python -m evals.run --tier standard

eval-nightly:
	APP_LLM_MODE=mock APP_TRACING_DISABLED=1 uv run python -m evals.run --tier nightly
