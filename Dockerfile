# Stage 1: Build React frontend
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python app
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY --from=frontend /app/src/static src/static

EXPOSE 6001

CMD ["uv", "run", "gunicorn", "-b", "0.0.0.0:6001", "--timeout", "120", "-k", "gevent", "--workers", "2", "src.main:app"]
