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
 
# Free, no API key needed: exercises routing/shape/tracing/budget against a mock client.
# Not a quality signal - see evals/run.py's docstring. This is the default; APP_LLM_MODE is
# forced here so a stray `APP_LLM_MODE=live` in .env can't make a "fast" run silently cost money.
eval-fast:
	APP_LLM_MODE=mock uv run python -m evals.run --tier fast
 
# Costs real API money. Run deliberately, not routinely.
eval-fast-live:
	APP_LLM_MODE=live uv run python -m evals.run --tier fast
 
# NOTE: unlike fast/fast-live, these two don't force a mode - they inherit whatever APP_LLM_MODE
# is set to (mock by default). Worth adding the same explicit mock/live split before either is
# used for real - see docs/lessons-learned.md, this is a known, still-open gap.
eval-standard:
	uv run python -m evals.run --tier standard
 
eval-nightly:
	uv run python -m evals.run --tier nightly