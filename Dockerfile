# Image for the scheduled daily run (ADR 0009): `python -m app.publish` screens the default scope
# and uploads the report and its CelesTrak snapshot to the app's Tigris bucket, then exits.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    # Trace lines would go to a file that dies with the Machine; the run logs one JSON line instead.
    APP_TRACING_DISABLED=1

WORKDIR /app

# Dependencies first so code-only changes reuse this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY config ./config
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "app.publish"]
