# Development image for the FastAPI backend (placeholder; production image TBD, see ADR 0006).
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
COPY src ./src
RUN uv sync --no-dev
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "jewel.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
