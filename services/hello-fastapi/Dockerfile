# Build from the repo root, because uv.lock lives there:
#   docker build -f services/hello-fastapi/Dockerfile .
# (make hello-up does this through Compose.) The root .dockerignore decides what is sent.

# Same Python image in both stages: a venv's bin/python links to the interpreter that built
# it, so the runtime stage needs that interpreter at the same path.
ARG PYTHON_IMAGE=python:3.13.16-slim-trixie

# --- Stage 1: install the service and its locked dependencies into /app/.venv ---
FROM ${PYTHON_IMAGE} AS build
# Only the uv binary from uv's image (same version as the laptop); no Python download.
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /src

# Dependencies first, in their own layer: a code change then rebuilds in seconds without
# downloading anything. --frozen installs exactly what uv.lock says, and fails instead of
# re-resolving. Only this service's packages (--package), without dev tools (--no-dev).
COPY pyproject.toml uv.lock ./
COPY services/hello-fastapi/pyproject.toml services/hello-fastapi/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package hello-fastapi --no-install-workspace

# Then the code. --no-editable copies it into the venv, so the venv works on its own.
COPY services/hello-fastapi services/hello-fastapi
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package hello-fastapi --no-editable

# --- Stage 2: just Python and the venv; no uv, no source tree, no build cache ---
FROM ${PYTHON_IMAGE}
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1
# Not root: a bug in the app can't change the image's files or install anything.
USER app
EXPOSE 8000

# opentelemetry-instrument wraps uvicorn and instruments FastAPI before the app is imported.
# One process, no --workers and no --reload: both start child processes, which zero-code
# instrumentation does not support.
CMD ["opentelemetry-instrument", "uvicorn", "hello_fastapi.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
