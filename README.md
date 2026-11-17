# my-work-service-py

A modular FastAPI service for My Work. It stores user profiles with a unique handle and a display name in PostgreSQL.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run the service in Python 3.14.

```sh
uv python install
uv sync --locked --all-groups
cp -n .env.example .env
```

Start PostgreSQL using `./local/compose up --wait` from the local `my-cloud-hub` checkout. In the service's `.env`, set `APP_DATABASE_URL` to the Work database using your local credentials. The template uses `127.0.0.1:15433/app_db_work_dev` for this setup. Percent-encode special characters in the URL password. Then apply the migration and start the API from this repo.

```sh
uv run --locked --env-file .env alembic upgrade head
uv run --locked --env-file .env uvicorn app.main:app --reload --port 8080 --no-access-log --no-server-header
```

Open `http://127.0.0.1:8080/docs` for the dev API documentation. `GET /health/live` checks the process. `GET /health/ready` returns `503` until the service can read the migrated Users table.

## Users API

| Method and path | Behavior |
| --- | --- |
| `POST /api/v1/users` | Create a profile using `handle` and `display_name`. |
| `GET /api/v1/users?limit=20&offset=0` | List profiles ordered by creation time and ID, with a total count. The maximum page size is 100. |
| `GET /api/v1/users/{user_id}` | Fetch a profile by UUID. |
| `PATCH /api/v1/users/{user_id}` | Change its display name. |
| `DELETE /api/v1/users/{user_id}` | Delete it and return `204`. |

Handles are stored in lowercase. A duplicate handle returns `409` even when its case differs. Each profile contains `id`, `handle`, `display_name`, and `created_at`. Before a dev rollout, restrict access to approved callers through Cloud Run IAM.

## Configuration and errors

`APP_ENV` accepts `dev` and `prd`. Production disables interactive API documentation and requires explicit trusted hosts. `.env.example` contains local defaults.

Application errors use `application/problem+json` with `message`, `status`, and a stable `code`. An error can include a short `detail` when it helps a caller correct the request. Dependency failures in the Users API return `503` with `service_unavailable`. Both environments return sanitized errors. Use the server-generated `X-Request-ID` response header to correlate errors with application logs.

The documented startup command and VS Code launch configuration disable Uvicorn's server banner and access log. The application emits structured JSON with severity, request method, route template, status, duration, and request ID. Requests without a matched API route use `unmatched`. Unexpected request failures record an error type and request ID. Raw URLs, query strings, headers, request bodies, and exception messages stay out of these application request logs. Cloud Run collects its own request logs separately.

## Development workflow

Branch from `develop` for each feature and review the diff and local results before committing. Open the feature PR into `develop`. PRs targeting `develop` or `main`, and pushes to either branch, run the quality checks. The planned Cloud Run targets are `api-work-dev` from `develop` and `api-work-prd` from `main`, with local and dev validation before production promotion.

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest
uv run --locked bandit -r src alembic
uv export --locked --all-groups --no-emit-project --output-file /tmp/my-work-service-py-requirements.txt
uv run --locked pip-audit --strict --requirement /tmp/my-work-service-py-requirements.txt --require-hashes --disable-pip
```

### Test suites

`tests/unit` covers isolated Python logic such as settings validation. `tests/api` exercises the FastAPI routes and middleware in-process. Both suites run by default in pytest and VS Code and require no PostgreSQL server.

`tests/integration` runs Alembic and exercises the Users API against PostgreSQL. Set `TEST_DATABASE_URL` to a disposable PostgreSQL database named `work_service_test` before running the integration suite or the full suite with coverage.

```sh
uv run --locked pytest tests/integration
uv run --locked pytest tests --cov --cov-report=term-missing
```

GitHub Actions runs unit and API tests in `verify`, then provisions PostgreSQL for `integration`. It enforces the 80% coverage threshold on the two jobs' combined results.
