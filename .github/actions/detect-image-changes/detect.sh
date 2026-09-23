#!/usr/bin/env bash
# Detect whether files that affect the application container image have changed.
#
# Keep IMAGE_PATHS in sync with the Dockerfile (COPY lines plus the Dockerfile
# itself) and .dockerignore. Do not include Helm, Terraform, tests, docs, or
# GitHub workflows — those must not trigger an image rebuild.
#
# If the comparison base cannot be resolved, this script reports changed=true
# so a missing image is never deployed.
set -euo pipefail

IMAGE_PATHS=(
  Dockerfile
  .dockerignore
  Pipfile
  Pipfile.lock
  app
)

changed=false
base=""

log() {
  printf '%s\n' "$*"
}

case "${BASE_STRATEGY:?BASE_STRATEGY is required}" in
  previous-commit)
    before="${GITHUB_EVENT_BEFORE:-}"
    if [[ -z "${before}" || "${before}" =~ ^0+$ ]]; then
      if git rev-parse --verify --quiet HEAD^ >/dev/null; then
        base="HEAD^"
      else
        log "No previous commit found; treating image as changed."
        changed=true
      fi
    else
      base="${before}"
    fi
    ;;
  previous-tag)
    current_ref="${GITHUB_REF_NAME:-}"
    if [[ -z "${current_ref}" ]]; then
      log "GITHUB_REF_NAME is empty; treating image as changed."
      changed=true
    else
      previous_tag="$(git describe --tags --abbrev=0 --exclude "${current_ref}" 2>/dev/null || true)"
      if [[ -z "${previous_tag}" ]]; then
        log "No previous tag found; treating image as changed."
        changed=true
      else
        base="${previous_tag}"
      fi
    fi
    ;;
  *)
    log "Unknown BASE_STRATEGY: ${BASE_STRATEGY}" >&2
    exit 1
    ;;
esac

if [[ "${changed}" != "true" ]]; then
  log "Comparing image-related paths against ${base} (strategy=${BASE_STRATEGY})"
  if ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
    log "Base ref ${base} is not available; treating image as changed."
    changed=true
  else
    diff_files="$(git diff --name-only "${base}" HEAD -- "${IMAGE_PATHS[@]}")"
    if [[ -n "${diff_files}" ]]; then
      changed=true
      log "Image-related files changed:"
      printf '%s\n' "${diff_files}" | sed 's/^/ - /'
    else
      log "No image-related files changed."
    fi
  fi
fi

log "changed=${changed}"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "changed=${changed}" >> "${GITHUB_OUTPUT}"
fi
