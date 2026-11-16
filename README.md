# my-work-service-py

A modular FastAPI service for My Work. The first business feature is a user directory with a unique handle and display name for each user.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run the service in Python 3.14.

```sh
uv python install
uv sync --locked --all-groups
cp -n .env.example .env
uv run --locked --env-file .env uvicorn app.main:app --reload --port 8080 --no-access-log
```

Send `GET /health/live` to `http://127.0.0.1:8080`. The service returns `{"status":"alive"}`. Local API docs are available at `/docs`.

## Configuration and errors

`APP_ENV` accepts `dev` and `prd`. Production disables interactive API documentation and requires explicit trusted hosts. `.env.example` contains local defaults. Each application request receives a server-generated `X-Request-ID` and a JSON access log with the Cloud Logging `severity` field. Application errors use `application/problem+json` with a stable `code` and the same request ID.

## Development workflow

Branch from `develop` for each feature and review the diff and local results before committing. Open the feature PR into `develop`. PRs targeting `develop` or `main`, and pushes to either branch, run the quality checks. The planned Cloud Run targets are `api-work-dev` from `develop` and `api-work-prd` from `main`, with local and dev validation before production promotion.

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest --cov=app --cov-report=term-missing
uv run --locked bandit -r src
uv export --locked --all-groups --no-emit-project --output-file /tmp/my-work-service-py-requirements.txt
uv run --locked pip-audit --strict --requirement /tmp/my-work-service-py-requirements.txt --require-hashes --disable-pip
```
