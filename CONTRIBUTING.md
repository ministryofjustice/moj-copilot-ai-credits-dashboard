# Contributing

This is the developer-facing companion to [README.md](README.md), which covers
what the app shows and how it works conceptually. This doc covers running it,
configuring it, testing it, extending it, and deploying it.

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
| `REPORTS_SOURCE` | `local` (default) \| `db` |
| `REPORTS_DIR` | Local backend root (default `reports`) |
| `REPORTS_CACHE_TTL` | Seconds to memoise reads (default `300`, prod `3600`, `0` disables and rebuilds the source per call) |
| `ATHENA_DATABASE` / `ATHENA_TABLE_MODELS` / `ATHENA_TABLE_USERS` | Athena backend |
| `ATHENA_WORKGROUP` / `ATHENA_OUTPUT_LOCATION` | Athena execution config |
| `AWS_DEFAULT_REGION` | AWS region for Athena (default `eu-west-2`) |

No secrets are committed to this repo; deployed environments inject them via
Kubernetes secrets and GitHub Actions secrets.

## Authentication

Access is gated by **Auth0**. `@requires_auth` enforces a signed-in session and
`@requires_admin` checks an org-role claim on the user's `userinfo`. Login,
callback, and logout are handled in `app/main/routes/auth.py`.

## Adding a new backend

`ReportsSource` (`app/main/services/reports_source.py`) is an abstract base
class with two methods: `model_rows()` and `user_rows()`, each returning plain
dict rows in the shapes described in the README's data model section. To add
a backend:

1. Subclass `ReportsSource` and implement both methods, returning rows in the
   same shape as the existing backends (see `db_reports_source.py` for
   reference).
2. Register it in `_build_source()`'s `if backend ==` chain, gated by a new
   `REPORTS_SOURCE` value.

Nothing else needs to change — `get_reports_source()` wraps any backend in the
same TTL cache, and `ai_credits.py`'s view-model code only ever sees the plain
row-lists, so it's backend-agnostic by construction.

## Frontend assets

GOV.UK Frontend, MoJ Frontend, Chart.js, and the `chartjs-chart-treemap`
plugin are **vendored**: committed as static files under
`app/static/javascript/` and `app/static/stylesheets/`, and served from this
app (`url_for('static', ...)` in `app/templates/components/base.html` and the
page templates) rather than pulled from a CDN `<script src="https://...">` at
request time.

This is deliberate — it avoids the class of "JS gremlin" that comes from
depending on a third party at runtime:

* **No CDN on the request path.** A CDN outage, a yanked/changed package
  version, or a compromised CDN serving different JS than what was reviewed
  can't silently affect this app, because nothing is fetched over the network
  when a page loads.
* **No Subresource Integrity bookkeeping.** Self-hosted files don't need SRI
  hashes — the file committed to the repo is byte-for-byte the file served.
* **A visible diff on upgrade, not a silent version bump.** The Chart.js
  files even carry their upstream version and source URL in a header comment
  (e.g. `chart.umd.min.js` is Chart.js v4.4.3 from
  `/npm/chart.js@4.4.3/dist/chart.umd.js`), so bumping a library is a
  reviewable file replacement, not a floating `^4.0.0` in a manifest.

To upgrade one of these libraries: download the new minified build from its
official release/CDN, replace the corresponding file under
`app/static/javascript/` or `app/static/stylesheets/` (keeping the existing
naming — GOV.UK Frontend's filename carries its version, e.g.
`govuk-frontend-5.1.0.min.js`), and note the version bump in the commit.

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

## Submitting changes

Suggestions and improvements are welcome — open a pull request or raise an issue.
