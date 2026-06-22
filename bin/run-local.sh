#!/usr/bin/env bash
#
# Run the AI Credits dashboard locally WITHOUT Auth0.
#
# AUTH_DISABLED makes the @requires_auth decorator a no-op
# (see app/main/middleware/auth.py). Never use this in a deployed env.
#
# Serves on http://localhost:4567/
#
set -euo pipefail

# Resolve repo root from this script's location so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Activate the local virtualenv (create with `pipenv install --dev` if missing).
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
else
  echo "No .venv found. Create it first, e.g.:" >&2
  echo "  pipenv install --dev   # or: python -m venv .venv && pip install -r requirements-dev.txt" >&2
  exit 1
fi

# Local-dev environment.
export AUTH_DISABLED=true             # bypass Auth0 login
export APP_SECRET_KEY=dev             # Flask session signing key
export LOGGING_LEVEL=DEBUG
export REPORTS_CACHE_TTL=0            # read on-disk reports fresh on every request

echo "Starting on http://localhost:4567/ (AUTH_DISABLED=${AUTH_DISABLED})"
exec python -m app.run
