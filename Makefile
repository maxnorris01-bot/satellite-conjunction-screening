.PHONY: install lint format typecheck test screen eval-fast eval-fast-live eval-standard eval-nightly
 
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
