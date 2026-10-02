#!/usr/bin/env bash
# Detect whether files that affect the application container image have changed.
#
# Keep IMAGE_PATHS in sync with the Dockerfile (COPY lines plus the Dockerfile
# itself) and .dockerignore. Do not include Helm, Terraform, tests, docs, or
# GitHub workflows — those must not trigger an image rebuild.
#
# Base selection depends on BASE_STRATEGY:
#   deployed-image   Dev, for both push to main and workflow_dispatch.
#                    Compare HEAD to the tag of the image currently running
#                    in the dev cluster (deployment
#                    moj-copilot-ai-credits-dashboard, container 0).
#   previous-tag     Production. Compare HEAD to the most recent tag other
#                    than the current ref. This path does not read the cluster.
#
# If the comparison base cannot be resolved, this script reports changed=true
# so a missing image is never deployed. For deployed-image that includes a
# missing deployment, a tag that is not a git commit, and any kubectl failure.
set -euo pipefail

IMAGE_PATHS=(
  Dockerfile
  .dockerignore
  Pipfile
  Pipfile.lock
  app
)

DEPLOYMENT_NAME="moj-copilot-ai-credits-dashboard"

changed=false
base=""

log() {
  printf '%s\n' "$*"
}

# Read the image tag currently deployed in the cluster: the part after the
# last ':' once any @sha256 digest is removed. Uses KUBE_CERT, KUBE_CLUSTER,
# KUBE_TOKEN, and KUBE_NAMESPACE — the same values the deploy job configures.
# Returns 1 so the caller can fail open.
read_deployed_image_tag() {
  DEPLOYED_IMAGE_TAG=""

  if [[ -z "${KUBE_CERT:-}" || -z "${KUBE_CLUSTER:-}" || -z "${KUBE_TOKEN:-}" || -z "${KUBE_NAMESPACE:-}" ]]; then
    log "Cluster credentials are incomplete; treating image as changed."
    return 1
  fi

  if ! command -v kubectl >/dev/null 2>&1; then
    log "kubectl is not available; treating image as changed."
    return 1
  fi

  local kube_dir
  if ! kube_dir="$(mktemp -d)"; then
    log "Could not create a temporary directory; treating image as changed."
    return 1
  fi
  # kube_dir is still in scope when this RETURN trap runs.
  trap 'rm -rf -- "${kube_dir}" || true' RETURN

  if ! printf '%s\n' "${KUBE_CERT}" > "${kube_dir}/ca.crt"; then
    log "Could not write the cluster CA certificate; treating image as changed."
    return 1
  fi

  local kubeconfig="${kube_dir}/config"

  # Same cluster, user, and context setup as the deploy job. A private
  # kubeconfig keeps this lookup from touching the runner's default config.
  if ! kubectl config set-cluster "${KUBE_CLUSTER}" \
    --kubeconfig "${kubeconfig}" \
    --certificate-authority="${kube_dir}/ca.crt" \
    --server="https://${KUBE_CLUSTER}"; then
    log "kubectl could not configure the cluster; treating image as changed."
    return 1
  fi

  if ! kubectl config set-credentials deploy-user \
    --kubeconfig "${kubeconfig}" \
    --token="${KUBE_TOKEN}"; then
    log "kubectl could not configure credentials; treating image as changed."
    return 1
  fi

  if ! kubectl config set-context "${KUBE_CLUSTER}" \
    --kubeconfig "${kubeconfig}" \
    --cluster="${KUBE_CLUSTER}" \
    --user=deploy-user \
    --namespace="${KUBE_NAMESPACE}"; then
    log "kubectl could not configure the context; treating image as changed."
    return 1
  fi

  if ! kubectl config use-context "${KUBE_CLUSTER}" --kubeconfig "${kubeconfig}"; then
    log "kubectl could not select the context; treating image as changed."
    return 1
  fi

  local current_image
  if ! current_image="$(kubectl get deployment "${DEPLOYMENT_NAME}" \
    --kubeconfig "${kubeconfig}" \
    --namespace "${KUBE_NAMESPACE}" \
    --output jsonpath='{.spec.template.spec.containers[0].image}')"; then
    log "Could not read deployment ${DEPLOYMENT_NAME}; treating image as changed."
    return 1
  fi

  if [[ -z "${current_image}" ]]; then
    log "No deployment image found; treating image as changed."
    return 1
  fi

  # Drop a digest first (repo:tag@sha256:...), then take the tag after the
  # last colon. Doing it in that order keeps a registry port or the digest
  # from being treated as the tag.
  local image_ref tag
  image_ref="${current_image%%@*}"
  tag="${image_ref##*:}"
  if [[ -z "${tag}" || "${tag}" == "${image_ref}" ]]; then
    log "Could not determine the deployed image tag from '${current_image}'; treating image as changed."
    return 1
  fi

  DEPLOYED_IMAGE_TAG="${tag}"
  log "Deployed image tag is ${tag} (${current_image})."
  return 0
}

case "${BASE_STRATEGY:?BASE_STRATEGY is required}" in
  # Dev push and workflow_dispatch. Compare against the SHA running in the
  # cluster. Any lookup failure fails open to changed=true.
  deployed-image)
    DEPLOYED_IMAGE_TAG=""
    if read_deployed_image_tag; then
      base="${DEPLOYED_IMAGE_TAG}"
    else
      changed=true
    fi
    ;;
  # Production releases. Leave this comparison on tags; do not read the cluster.
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
