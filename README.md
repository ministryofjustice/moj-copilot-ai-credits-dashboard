# 📊 MoJ Copilot AI Credits Dashboard

A Flask web app that visualises GitHub Copilot **AI-credit usage** across the
Ministry of Justice enterprise. It gives individual users a view of their own
spend against their plan allowance, and gives admins pooled, weekly, and daily
views across the whole org.

The app is **read-only**: it renders usage data that is captured elsewhere and
handed to it as a partitioned Parquet dataset. It never calls the GitHub API and
never writes to its data source.

## What it shows

| Route | Page | Audience | Key query params |
|-------|------|----------|------------------|
| `/` | **My usage** | Any signed-in user | `?user=<login>&plan=<plan>&month=<YYYY-MM>` |
| `/admin/pooled` | **Org pooled** | Admins | `?period=weekly\|monthly&plan=<plan>&seats=<n>` |
| `/admin/weekly` | **Org weekly** | Admins | `?plan=<plan>&week=YYYY-Www` |
| `/admin/daily` | **Org daily** | Admins | `?day=YYYY-MM-DD` |

All view state is carried in the URL query string (the Flask-idiomatic
replacement for the reactive widgets of the Streamlit app this was ported from),
so pages are shareable and bookmarkable. Charts are rendered client-side with
Chart.js; the server ships plain JSON-serialisable view models.

## How it works

```
                 ┌─────────────────────────────────────────┐
   Parquet       │  ReportsSource (abstract)                │
   dataset  ───► │    • LocalFsReportsSource  (reports/)    │ ──► view-model
  (2 tables)     │    • S3ReportsSource       (S3 bucket)   │     builders ──► Jinja + Chart.js
                 │    • DbReportsSource       (Athena)      │     (ai_credits.py)
                 └─────────────────────────────────────────┘
```

### The data model

The data is a two-table dataset, Hive-partitioned by `day` (`day=YYYY-MM-DD/`):

* **`credits_by_model`** → `{day, model, model_family, routed, credits}` — the
  org-level per-model split (`routed` is `True` for `Auto:`-prefixed models).
* **`credits_by_user`** → `{day, user_login, credits}` — per-user daily totals
  (there is **no** per-model breakdown per user in this data).

Every backend returns these same plain row-lists, so the view-model code in
`app/main/services/ai_credits.py` is completely backend-agnostic and unit-testable.

### Data backends (`REPORTS_SOURCE`)

The source is resolved per request by `get_reports_source()` and selected with
the `REPORTS_SOURCE` env var:

| Value | Backend | Reads from | Used in |
|-------|---------|------------|---------|
| `local` (default) | `LocalFsReportsSource` | `reports/` on disk | local dev |
| `s3` | `S3ReportsSource` | S3 bucket (pyarrow) | — |
| `db` | `DbReportsSource` | Athena over the Parquet | production |

For `s3`/`db`, AWS credentials are resolved by the default AWS chain (IRSA / the
pod's service-account role) — **no static keys are read or stored**. Reads are
memoised for `REPORTS_CACHE_TTL` seconds (default 300) since the data updates
roughly once a day.

> **Note on the data:** the `reports/` directory (the raw usage data) is
> `.gitignore`d and is **never committed** — it may contain user/billing data.
> In production the data lives in S3/Athena and is reached via the pod's IAM
> role. The pipeline that *builds* the Parquet dataset lives outside this repo.

## Directory structure

```bash
.
├── app/
│   ├── app.py                       # Application factory entry point
│   ├── run.py                       # `python -m app.run` dev runner
│   └── main/
│       ├── config/                  # Modular config (auth0, cors, logging, ...)
│       ├── middleware/
│       │   ├── auth.py              # @requires_auth / @requires_admin (Auth0)
│       │   └── error_handler.py
│       ├── routes/
│       │   ├── ai_credits.py        # The dashboard pages
│       │   ├── auth.py              # Auth0 login/callback/logout
│       │   └── robots.py
│       ├── services/
│       │   ├── ai_credits.py        # View-model builders (no Flask, no I/O)
│       │   ├── reports_source.py    # ReportsSource abstraction + local backend
│       │   ├── s3_reports_source.py # S3 backend
│       │   ├── db_reports_source.py # Athena backend
│       │   ├── caching_reports_source.py  # TTL cache wrapper
│       │   ├── weekly_per_user.py   # Weekly roll-up maths
│       │   └── auth0_service.py
│       ├── static/                  # JS (Chart.js glue), CSS, images
│       └── templates/               # GOV.UK-styled Jinja templates
├── bin/                             # Dev/ops helper scripts (see below)
├── helm/application/                # Helm chart for MoJ Cloud Platform
├── reports/                         # Local usage data (gitignored)
├── test/                            # pytest suite
├── Dockerfile
├── docker-compose.yaml
└── makefile
```

## Running locally

The quickest path bypasses Auth0 and reads the on-disk `reports/` data.

### Option A — native (no Auth0)

```bash
pipenv install --dev        # create the virtualenv & install deps
./bin/run-local.sh          # sets AUTH_DISABLED=true and serves on :4567
```

`AUTH_DISABLED=true` turns the `@requires_auth` decorator into a no-op so you can
run without a reachable Auth0 tenant. **Never enable it in a deployed env.** With
auth disabled, the *My usage* page stands in a random top-spender so the page
renders with real-shaped data; override with `?user=<login>`.

The app is served at <http://localhost:4567/>.

> You need a populated `reports/` directory locally for the `local` backend to
> return data. Its layout is `reports/credits_by_{model,user}/day=YYYY-MM-DD/part-0.parquet`.

## Configuration

All config is read from environment variables (see `app/main/config/`).

| Variable | Purpose |
|----------|---------|
| `APP_SECRET_KEY` | Flask session signing key |
| `APP_ENV` | Environment label (`local` / `development` / `production`) |
| `AUTH_DISABLED` | Local-only escape hatch to bypass Auth0 |
| `LOGGING_LEVEL` | e.g. `DEBUG`, `INFO` |
| `AUTH0_DOMAIN` / `AUTH0_CLIENT_ID` / `AUTH0_CLIENT_SECRET` | Auth0 tenant + app |
| `REPORTS_SOURCE` | `local` (default) \| `s3` \| `db` |
| `REPORTS_DIR` | Local backend root (default `reports`) |
| `REPORTS_CACHE_TTL` | Seconds to memoise reads (default `300`, `0` disables) |
| `REPORTS_S3_BUCKET` / `REPORTS_S3_PREFIX` | S3 backend location |
| `ATHENA_DATABASE` / `ATHENA_TABLE_MODELS` / `ATHENA_TABLE_USERS` | Athena backend |
| `ATHENA_WORKGROUP` / `ATHENA_OUTPUT_LOCATION` | Athena execution config |
| `AWS_DEFAULT_REGION` | AWS region for S3/Athena (default `eu-west-2`) |

No secrets are committed to this repo; deployed environments inject them via
Kubernetes secrets and GitHub Actions secrets.

## Authentication

Access is gated by **Auth0**. `@requires_auth` enforces a signed-in session and
`@requires_admin` checks an org-role claim on the user's `userinfo`. Login,
callback, and logout are handled in `app/main/routes/auth.py`.

## Testing

```bash
pipenv run pytest                 # run the suite
pipenv run tests                  # coverage run -m pytest test
pipenv run tests_report           # coverage report
```

## Linting

```bash
make flake8      # flake8 (config in .flake8)
make lint        # full MegaLinter run
pipenv run pylint app
```

`flake8`, `pylint`, and `black` are enforced, with MegaLinter running in CI.

## Deployment

The app deploys to the **MoJ Cloud Platform** (Kubernetes) via the Helm chart in
`helm/application/`. Per-environment values live in `values-dev.yaml` and
`values-prod.yaml`; production reads its data through the Athena (`db`) backend.

CI/CD is defined in `.github/workflows/` (build, test, Trivy scans, MegaLinter,
and deploy-to-dev / deploy-to-prod). All credentials come from GitHub Actions
secrets.

```bash
helm upgrade --install moj-copilot-ai-credits-dashboard ./helm/application \
  -f ./helm/application/values-<env>.yaml
```

## Template provenance & helper tooling

This project was bootstrapped from the MoJ Operations Engineering
[**Flask template**](https://github.com/ministryofjustice/operations-engineering-flask-template),
and it keeps several useful pieces of that template's scaffolding:

* **Structured Flask layout** — application factory, blueprints, and modular
  per-concern config under `app/main/config/`.
* **Dependency management with Pipenv** (`Pipfile` / `Pipfile.lock`).
* **Docker** support (`Dockerfile`, `docker-compose.yaml`) and a `makefile` that
  wraps the common build/run/lint tasks.
* **Helm charts** for Cloud Platform deployments.
* **Pre-wired linting & testing** — `flake8`, `pylint`, `black`, MegaLinter, and
  `pytest` with coverage.
* **Error-handling middleware** 

Helper scripts are retained in `bin/` 


## Contributing

Suggestions and improvements are welcome — open a pull request or raise an issue.

## Licence

Licensed under the [MIT License](LICENSE). © Crown Copyright (Ministry of Justice).
