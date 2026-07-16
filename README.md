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

The **My usage** page also renders a rolling calendar heatmap of daily usage
(GitHub-contributions-graph style): each day is bucketed into one of 6 levels
based on its usage as a percentage of the daily allowance (`<25%`, `<50%`,
`<100%`, `<150%`, `<300%`, `≥300%`), so heavy days stand out at a glance.

### Projected usage

The **My usage** and **Org pooled** pages both project where the month will
land if the current daily pace continues, alongside the cumulative
credits-so-far chart:

* Once at least 5 days into the month (and before it's finished), the
  month-to-date total is extrapolated straight-line to a full-month figure:
  `mtd ÷ days_elapsed × days_in_month`.
* The projection is labelled **over** / **under** / **on-track** against the
  relevant limit (the user's monthly allowance, or the pool's `seats × plan`
  allowance on the admin page), with a ±2% tolerance band so it doesn't flip
  labels on small day-to-day swings.
* The cumulative chart also overlays the **previous calendar month's** curve
  (aligned by day-of-month) so the current trend can be read against recent
  history.
* Completed months, and months with too little data yet (<5 days), show the
  cumulative curve without a projection.

## How it works

```text
                 ┌─────────────────────────────────────────┐
   Parquet       │  ReportsSource (abstract)                │
   dataset  ───► │    • LocalFsReportsSource  (reports/)    │ ──► view-model
  (2 tables)     │    • DbReportsSource       (Athena)      │     builders ──► Jinja + Chart.js
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
| `db` | `DbReportsSource` | Athena over the Parquet | production |

For `db`, AWS credentials are resolved by the default AWS chain (IRSA / the
pod's service-account role) — **no static keys are read or stored**. Reads are
memoised for `REPORTS_CACHE_TTL` seconds (default 300) since the data updates
roughly once a day.

### Auth0 Identity Solution
The Terraform for the identity solution can be found at `terrraform/auth0`.
This module is deployed via the `♻️ Terraform Auth0` pipeline.

## Module Inputs

| Input | Description | Required | Default |
| ------- | ------------- | ---------- | --------- |
| `auth0_domain` | value of the Auth0 domain | Yes | `''` |
| `auth0_client_id` | value of the Auth0 client id | Yes | `''` |
| `auth0_client_secret` | value of the Auth0 client secret | Yes | `''` |
| `github_oauth_client_id` | value of the GitHub OAuth client id | Yes | `''` |
| `github_oauth_client_secret` | value of the GitHub OAuth client secret | Yes | `''` |
| `webapp_domain` | Domain name of web application | Yes | `''` |
| `environment` | Application environment | Yes | `''` |

## Contributing

For running the app locally, configuration, testing, linting, deployment, and
how to extend it (e.g. adding a new data backend), see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Licensed under the [MIT License](LICENSE). © Crown Copyright (Ministry of Justice).
