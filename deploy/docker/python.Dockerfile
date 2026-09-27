# syntax=docker/dockerfile:1.7
# Platform API and Temporal worker images (same dependency closure, different entry points).
#   docker build -f deploy/docker/python.Dockerfile --target api    -t formal-agent-lab/api .
#   docker build -f deploy/docker/python.Dockerfile --target worker -t formal-agent-lab/worker .
ARG PYTHON_IMAGE=python:3.12-slim-trixie

FROM ghcr.io/astral-sh/uv:0.12.19 AS uv

FROM ${PYTHON_IMAGE} AS build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /src
COPY pyproject.toml uv.lock .python-version ./
COPY packages packages
COPY examples examples
COPY contracts contracts
# --frozen: exactly the versions in uv.lock; --no-dev: runtime closure only; --no-editable: source not needed later
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-packages --no-editable

FROM ${PYTHON_IMAGE} AS runtime
ARG FAL_SOURCE_REVISION=unknown
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FAL_SOURCE_REVISION=${FAL_SOURCE_REVISION} FAL_API_HOST=0.0.0.0 FAL_API_PORT=8000
RUN groupadd --system fal && useradd --system --gid fal --home /home/fal --create-home fal
COPY --from=build /opt/venv /opt/venv
WORKDIR /home/fal
USER fal
LABEL org.opencontainers.image.source="https://github.com/3351666087/formal-agent-lab" \
      org.opencontainers.image.revision="${FAL_SOURCE_REVISION}" \
      org.opencontainers.image.licenses="NOASSERTION"

FROM runtime AS api
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=12 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1
CMD ["fal-api"]

FROM runtime AS worker
CMD ["fal-worker"]
