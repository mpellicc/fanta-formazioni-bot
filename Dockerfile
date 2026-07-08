FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm
WORKDIR /app
RUN useradd --create-home appuser \
    && mkdir /data \
    && chown appuser /data
USER appuser
COPY --from=builder --chown=appuser /app/.venv /app/.venv
COPY --chown=appuser src ./src
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/src"
CMD ["python", "-m", "fantaformazionibot"]
