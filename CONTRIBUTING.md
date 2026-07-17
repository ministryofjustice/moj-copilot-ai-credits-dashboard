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
├── helm/moj-copilot-ai-credits-dashboard/                # Helm chart for MoJ Cloud Platform
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

### The contract

The row shape is the whole contract. Return exactly these keys, with `day` an
ISO `YYYY-MM-DD` **string**, `routed` a real `bool`, and `credits` a `float`:

```python
model_rows() -> [{"day": "2026-07-15", "model": "gpt-4o",
                  "model_family": "gpt-4o", "routed": False, "credits": 12.5}, ...]
user_rows()  -> [{"day": "2026-07-15", "user_login": "alice", "credits": 3.0}, ...]
```

Get those types right and every page, chart, and roll-up works unchanged. The
two existing backends are the reference: `LocalFsReportsSource` reads the
on-disk parquet tree, `DbReportsSource` runs two Athena queries.

### Sketch: a SQL backend

The most likely thing a fork needs is a database that isn't Athena — Postgres,
RDS/Aurora, Redshift, DuckDB. That is one new file and one factory branch. Below
is an illustrative sketch (SQLAlchemy Core, so one code path covers every
dialect); it is **not implemented here** and is not on our roadmap, but the seam
is designed to take it:

```python
# app/main/services/sql_reports_source.py
import os

from sqlalchemy import URL, create_engine, text

from app.main.services.reports_source import ReportsSource


def _iso(day) -> str:
    return day.isoformat() if hasattr(day, "isoformat") else str(day)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "t", "yes")


class SqlReportsSource(ReportsSource):
    def __init__(self, engine=None) -> None:
        self._engine = engine or create_engine(URL.create(
            "postgresql+psycopg",
            username=os.getenv("REPORTS_DB_USER"),
            password=os.getenv("REPORTS_DB_PASSWORD"),
            host=os.getenv("REPORTS_DB_HOST"),
            port=int(os.getenv("REPORTS_DB_PORT") or 5432),
            database=os.getenv("REPORTS_DB_NAME"),
        ), pool_pre_ping=True)
        self._model_table = os.getenv("REPORTS_TABLE_MODELS") or "credits_by_model"
        self._user_table = os.getenv("REPORTS_TABLE_USERS") or "credits_by_user"

    def model_rows(self) -> list[dict]:
        sql = text("SELECT model, model_family, routed, ai_credits_used, day "
                   f"FROM {self._model_table}")
        with self._engine.connect() as conn:
            return [{"day": _iso(r.day), "model": r.model,
                     "model_family": r.model_family, "routed": _as_bool(r.routed),
                     "credits": float(r.ai_credits_used)}
                    for r in conn.execute(sql)]

    def user_rows(self) -> list[dict]:
        sql = text(f"SELECT user_login, ai_credits_used, day FROM {self._user_table}")
        with self._engine.connect() as conn:
            return [{"day": _iso(r.day), "user_login": r.user_login,
                     "credits": float(r.ai_credits_used)}
                    for r in conn.execute(sql)]
```

Prefer explicit named env vars (`REPORTS_DB_HOST`, `REPORTS_DB_PORT`, …) over a
single opaque `REPORTS_DB_URL`, and build the URL internally — operators then set
clearly-named fields rather than a magic blob, and the password comes from a
Kubernetes secret like every other credential here.

**The one real trap is type coercion.** Athena's `GetQueryResults` API is
string-typed, so `db_reports_source.py` coerces everything by hand. SQLAlchemy
dialects hand back *typed* values instead, and the types differ per database:
`routed` arrives as a real `bool` from Postgres but often as `0/1` from
SQLite/DuckDB, and `day` may be a `date` object or a string depending on the
column type. Hence `_as_bool()` above, and the existing `_iso()`
(`day.isoformat() if hasattr(day, "isoformat") else str(day)`). Everything else
is boilerplate; this is the part to test.

### Sketch: DuckDB reading the Parquet directly

DuckDB is worth calling out because it can query the same S3 Parquet tree Athena
reads, with no managed service in front of it — a functional equivalent of the
`db` backend. It's embedded, so it takes a file path (or `:memory:`) rather than
host/port, and two things differ from the SQL sketch above.

The "table" stops being a table name and becomes an expression —
`hive_partitioning=1` is what recovers `day` from the `day=YYYY-MM-DD/`
directories (the same partition column the `local` backend reads via its `DAY`
spec):

```python
def _table_ref(name: str, *, duckdb_s3: bool) -> str:
    if duckdb_s3:  # name is an S3 prefix, e.g. s3://bucket/prefix/credits_by_model
        return f"read_parquet('{name}/**/*.parquet', hive_partitioning=1)"
    return name    # a real SQL table for every other engine
```

And every *physical* connection needs the `httpfs` extension plus credentials,
since a fresh DuckDB connection starts with neither:

```python
from sqlalchemy import event

engine = create_engine("duckdb:///:memory:")  # only ever reads remote parquet


@event.listens_for(engine, "connect")
def _prepare(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("INSTALL httpfs; LOAD httpfs;")
    # credential_chain resolves the pod's IRSA role via the same boto3 chain the
    # Athena backend uses — no static keys.
    cur.execute("CREATE SECRET IF NOT EXISTS s3read "
                "(TYPE S3, PROVIDER credential_chain, REGION 'eu-west-2');")
    cur.close()
```

Everything after the `FROM` — the column list, `_as_bool(r.routed)`, `_iso(r.day)`
— is unchanged, because `read_parquet` exposes the parquet columns plus the Hive
partition column under the same names. That's the point of freezing the row
shape: DuckDB-over-S3 is a different `FROM`, not a different dashboard.

### Testing a new backend

Point it at a real in-memory SQLite or DuckDB database rather than mocking a
client: create the two tables, insert a couple of rows, assert both row-lists,
and add a factory test that your `REPORTS_SOURCE` value builds your class. That
exercises the coercion above, which a mock would paper over.

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
`helm/moj-copilot-ai-credits-dashboard/`. Per-environment values live in `values-dev.yaml` and
`values-prod.yaml`; production reads its data through the Athena (`db`) backend.

CI/CD is defined in `.github/workflows/` (build, test, SCA, MegaLinter,
and deploy-to-dev / deploy-to-prod). All credentials come from GitHub Actions
secrets.

```bash
helm upgrade --install moj-copilot-ai-credits-dashboard ./helm/moj-copilot-ai-credits-dashboard \
  -f ./helm/moj-copilot-ai-credits-dashboard/values-<env>.yaml
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

## Contributions, forks, and governance

This dashboard is built and maintained for the Ministry of Justice's own use, and
its direction is set by our internal roadmap and governance plans. That shapes
what we can take from outside:

* **Issues are always welcome.** Bug reports, questions, and "have you
  considered…" are useful to us regardless of whether we act on them.
* **Pull requests are welcome, but we can only merge what coincides with our
  roadmap.** Every line we merge is a line we maintain and deploy, so a PR is
  judged on whether it fits where we're already going — not just on whether it's
  good work. If you're planning anything beyond a small fix, **open an issue
  first** and let's check the fit before you spend the effort. We'd rather say
  "not for us" early than after you've written it.
* **Fork it.** It's [MIT](LICENSE) — you're free to take it, run it, and change
  it, and you don't need our permission or our agreement. If your needs diverge
  from ours, forking is a legitimate answer rather than a consolation prize.

### Diverging without pain

If you fork, the seam designed for you is `ReportsSource`. Your data almost
certainly doesn't live where ours does, and that's the one thing the app is
explicitly built to let you swap: subclass the ABC, return the two row-lists,
register your backend in `_build_source()` (see [Adding a new
backend](#adding-a-new-backend), which sketches SQL and DuckDB backends we
haven't built ourselves).

Keeping your changes behind that seam is the difference between a fork you can
rebase and a fork you can't. Everything downstream — the view-model builders, the
caching wrapper, the templates, the charts — only ever sees the plain row-lists,
so a new backend touches one new file and one factory branch. Changes scattered
through `ai_credits.py` or the templates will fight every upstream pull; a
backend won't.

And if you build a backend you think we'd want, the roadmap caveat still applies
— but a self-contained backend is about the most mergeable thing you could send
us, so do open that issue.
