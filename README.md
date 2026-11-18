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

## Run in Docker

Build and start the API on a loopback port. The image runs one Uvicorn worker as a non-root user and listens on `PORT`, which defaults to `8080`.

```sh
docker build -t my-work-service-py:local .
docker run --rm -p 127.0.0.1:18080:8080 my-work-service-py:local
```

From a second terminal, run `curl -fsS http://127.0.0.1:18080/health/live`. For Users and readiness checks, start the local homelab Compose stack and attach the API to its `my-cloud-hub-local_default` network. Create `.env.container` with your existing Work database name and URL-encoded local password. Container-to-container connections use `postgres:5432`.

```dotenv
APP_ENV=dev
APP_DATABASE_URL=postgresql://postgres:<LOCAL_POSTGRES_PASSWORD>@postgres:5432/<WORK_DATABASE_NAME>
```

The build uses a file allowlist. Supply secrets at runtime through `.env.container`, which Git ignores. If you add list settings such as `APP_ALLOWED_HOSTS`, write the JSON value without surrounding single quotes for Docker's env-file parser.

Apply migrations once, then start the database-backed API and check `/health/ready` in a second terminal.

```sh
docker run --rm --network my-cloud-hub-local_default --env-file .env.container \
  my-work-service-py:local alembic upgrade head
docker run --rm --network my-cloud-hub-local_default --env-file .env.container \
  -p 127.0.0.1:18080:8080 my-work-service-py:local
```

For a Cloud Run build, target `linux/amd64`. The container uses the same `PORT` setting for local and Cloud Run startup.

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

### Cloud Run dev database settings

In Secret Manager, add a version of the existing `app-secrets-dev` bundle with one new entry and preserve its other keys. Use the runtime password you set for `work_api_dev_runtime` and percent-encode special characters in it. The entry for the Work API has this shape within the larger JSON object.

```json
{
  "WORK_API_DATABASE_URL": "postgresql://work_api_dev_runtime:<URL_ENCODED_RUNTIME_PASSWORD>@<VM_INTERNAL_IP>:5432/app_db_work_dev"
}
```

Apply the Work API dev runtime configuration in `my-cloud-hub` before the first application rollout. Terraform sets `APP_ENV=dev`, `APP_ALLOWED_HOSTS`, and the `APP_SECRETS` reference to `app-secrets-dev:latest` for `cloudrun-runtime-dev`. The deployment workflow sets Direct VPC egress on `default/default` with `private-ranges-only` so the service can reach the VM. [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets) · [Direct VPC egress](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc)

When `APP_SECRETS` is present, the API selects `WORK_API_DATABASE_URL` from the bundle and validates the runtime login and database against `APP_ENV`. Otherwise, it uses `APP_DATABASE_URL` for local development. Alembic always uses its own `APP_DATABASE_URL`. Keep the migration credential separate from the bundle mounted into the API.

## Development workflow

Branch from `develop` for each feature and review the diff and local results before committing. Open the feature PR into `develop`. PRs targeting `develop` or `main` and pushes to `main` run the quality checks. A push to `develop` runs those same checks before deploying to the private `api-work-dev` Cloud Run service.

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

### Deploy and verify dev

1. In `my-cloud-hub`, apply the Work API dev deployment identity, its `work-api-dev` Artifact Registry repository, and its Cloud Run runtime configuration. Apply the dev database migration and confirm the runtime role has access to `public.users`.
2. Set `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_DEPLOY_SERVICE_ACCOUNT` in this repository's **Settings → Secrets and variables → Actions → Variables**. Use the identifiers from the infra output `work_api_dev_deployment_identity`.
3. Merge the app PR into `develop`. The workflow builds the Linux AMD64 image, authenticates through Workload Identity Federation, pushes it to the dev registry, and updates Cloud Run by digest. The rollout waits for the new image to serve traffic. If traffic is pinned after a manual rollback, review the dev traffic assignment before restoring latest-revision routing.
4. Run the authenticated proxy with your existing Cloud Run access. From a second terminal, check liveness and database readiness. Expect `{"status":"alive"}` and `{"status":"ready"}`.

```sh
gcloud run services proxy api-work-dev --project="$GCP_PROJECT_ID" --region=us-central1 --port=18080
```

```sh
curl -fsS http://127.0.0.1:18080/health/live
curl -fsS http://127.0.0.1:18080/health/ready
```

The Cloud Run rollout result confirms the revision is serving traffic. The readiness request confirms that the runtime identity and PostgreSQL login can read the migrated Users table. Keep the previous Secret Manager version available until this check passes.
