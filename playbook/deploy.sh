#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

APP_NAME="${APP_NAME:-bosgenesis-mop-creation-agent}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-bosgenesis-mop-creation-agent}"
IMAGE_TAG="${IMAGE_TAG:-0.0.1}"
IMAGE="${IMAGE_REPOSITORY}:${IMAGE_TAG}"
IMAGE_TAR="${IMAGE_REPOSITORY}-${IMAGE_TAG}.tar"
NAMESPACE="${NAMESPACE:-bosgenesis}"
REMOTE_USER="${REMOTE_USER:-taieuser}"
REMOTE_HOST="${REMOTE_HOST:-10.99.52.165}"
REMOTE_TMP_DIR="${REMOTE_TMP_DIR:-/tmp}"
REMOTE_IMAGE_TAR="${REMOTE_TMP_DIR}/${IMAGE_TAR}"
DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-bosgenesis-mop-creation-agent}"
CONTAINER_NAME="${CONTAINER_NAME:-bosgenesis-mop-creation-agent}"
DEPLOY_METHOD="${DEPLOY_METHOD:-helm}"
HELM_RELEASE="${HELM_RELEASE:-bosgenesis-mop-creation-agent}"
HELM_CHART="${HELM_CHART:-charts/bosgenesis-mop-creation-agent}"
HELM_VALUES_FILE="${HELM_VALUES_FILE:-}"
KUSTOMIZE_DIR="${KUSTOMIZE_DIR:-deploy/k8s}"
SKIP_BUILD="${SKIP_BUILD:-false}"
SKIP_IMAGE_TRANSFER="${SKIP_IMAGE_TRANSFER:-false}"
ENABLE_INGRESS="${ENABLE_INGRESS:-true}"
INGRESS_HOST="${INGRESS_HOST:-mop-creation-agent.bosgenesis.local}"
INGRESS_CLASS_NAME="${INGRESS_CLASS_NAME:-nginx}"
INGRESS_PATH="${INGRESS_PATH:-/}"
INGRESS_PATH_TYPE="${INGRESS_PATH_TYPE:-Prefix}"
LANGFUSE_ENABLED="${LANGFUSE_ENABLED:-true}"
SIGNOZ_ENABLED="${SIGNOZ_ENABLED:-true}"
QDRANT_RETRIEVAL_ENABLED="${QDRANT_RETRIEVAL_ENABLED:-true}"
SOURCE_NAMESPACE="${SOURCE_NAMESPACE:-bosgenesis}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

log() {
  printf '\n[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 127
  fi
}

adopt_helm_resource() {
  local kind="$1"
  local name="$2"

  if kubectl get "${kind}" "${name}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    log "Adopting existing ${kind}/${name} into Helm release ${HELM_RELEASE}"
    kubectl label "${kind}" "${name}" \
      app.kubernetes.io/managed-by=Helm \
      -n "${NAMESPACE}" \
      --overwrite
    kubectl annotate "${kind}" "${name}" \
      meta.helm.sh/release-name="${HELM_RELEASE}" \
      meta.helm.sh/release-namespace="${NAMESPACE}" \
      -n "${NAMESPACE}" \
      --overwrite
  fi
}

adopt_existing_helm_resources() {
  if helm status "${HELM_RELEASE}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    return
  fi

  log "Checking for existing non-Helm resources to adopt"
  adopt_helm_resource configmap "${DEPLOYMENT_NAME}-config"
  adopt_helm_resource persistentvolumeclaim "${DEPLOYMENT_NAME}-mops"
  adopt_helm_resource service "${DEPLOYMENT_NAME}"
  adopt_helm_resource deployment "${DEPLOYMENT_NAME}"
  adopt_helm_resource ingress "${DEPLOYMENT_NAME}"
}

validate_helm_chart_files() {
  local helmignore_file="${HELM_CHART}/.helmignore"

  if [ -f "${helmignore_file}" ] && grep -F "**" "${helmignore_file}" >/dev/null 2>&1; then
    echo "Unsupported Helm ignore pattern found in ${helmignore_file}: double-star (**) is not supported by this Helm version." >&2
    echo "Use explicit single-level patterns such as templates/SPEC.md instead." >&2
    exit 1
  fi
}

require_cmd kubectl
require_cmd ssh
require_cmd scp

if [ "${DEPLOY_METHOD}" = "helm" ]; then
  require_cmd helm
  validate_helm_chart_files
fi

if [ "${SKIP_BUILD}" != "true" ]; then
  require_cmd docker
  log "Building image ${IMAGE}"
  docker build -t "${IMAGE}" .

  log "Saving image to ${IMAGE_TAR}"
  docker save "${IMAGE}" -o "${IMAGE_TAR}"
fi

if [ "${SKIP_IMAGE_TRANSFER}" != "true" ]; then
  log "Copying image tar to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_IMAGE_TAR}"
  scp "${IMAGE_TAR}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_IMAGE_TAR}"

  log "Importing image into containerd on ${REMOTE_HOST}"
  ssh "${REMOTE_USER}@${REMOTE_HOST}" "sudo ctr -n k8s.io images import '${REMOTE_IMAGE_TAR}'"

  log "Verifying imported image on ${REMOTE_HOST}"
  ssh "${REMOTE_USER}@${REMOTE_HOST}" "sudo ctr -n k8s.io images list | grep '${IMAGE_REPOSITORY}'"
fi

log "Ensuring namespace ${NAMESPACE} exists"
kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"

if [ "${DEPLOY_METHOD}" = "helm" ]; then
  ROLLOUT_TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  log "Deploying with Helm release ${HELM_RELEASE}"
  adopt_existing_helm_resources

  helm_args=(
    upgrade
    --install
    "${HELM_RELEASE}"
    "${HELM_CHART}"
    --namespace "${NAMESPACE}"
    --set image.repository="${IMAGE_REPOSITORY}"
    --set image.tag="${IMAGE_TAG}"
    --set ingress.enabled="${ENABLE_INGRESS}"
    --set ingress.hosts[0].host="${INGRESS_HOST}"
    --set ingress.hosts[0].paths[0].path="${INGRESS_PATH}"
    --set ingress.hosts[0].paths[0].pathType="${INGRESS_PATH_TYPE}"
    --set rolloutTimestamp="${ROLLOUT_TIMESTAMP}"
    --set config.agent.source_namespace="${SOURCE_NAMESPACE}"
    --set config.logging.level="${LOG_LEVEL}"
    --set config.observability.langfuse_enabled="${LANGFUSE_ENABLED}"
    --set config.observability.signoz_enabled="${SIGNOZ_ENABLED}"
    --set config.retrieval.qdrant.enabled="${QDRANT_RETRIEVAL_ENABLED}"
  )
  if [ -n "${INGRESS_CLASS_NAME}" ]; then
    helm_args+=(--set ingress.className="${INGRESS_CLASS_NAME}")
  fi
  if [ -n "${HELM_VALUES_FILE}" ]; then
    helm_args+=(-f "${HELM_VALUES_FILE}")
  fi
  helm "${helm_args[@]}"
else
  log "Applying Kubernetes manifests from ${KUSTOMIZE_DIR}"
  kubectl apply -k "${KUSTOMIZE_DIR}"

  if [ "${ENABLE_INGRESS}" = "true" ]; then
    log "Ensuring ingress is applied"
    kubectl apply -f "${KUSTOMIZE_DIR}/ingress.yaml"
  else
    log "Ingress disabled; deleting ingress if present"
    kubectl delete ingress "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --ignore-not-found=true
  fi

  log "Setting deployment image to ${IMAGE}"
  kubectl set image "deployment/${DEPLOYMENT_NAME}" \
    "${CONTAINER_NAME}=${IMAGE}" \
    -n "${NAMESPACE}"
fi

log "Waiting for rollout"
kubectl rollout status "deployment/${DEPLOYMENT_NAME}" -n "${NAMESPACE}"

log "Deployment containers"
kubectl get deployment "${DEPLOYMENT_NAME}" \
  -n "${NAMESPACE}" \
  -o jsonpath='{.spec.template.spec.containers[*].name}'
echo

log "Pods"
kubectl get pod -n "${NAMESPACE}" -o wide | grep "${DEPLOYMENT_NAME}" || true

log "Service"
kubectl get svc "${DEPLOYMENT_NAME}" -n "${NAMESPACE}"

if [ "${ENABLE_INGRESS}" = "true" ]; then
  log "Ingress"
  kubectl get ingress "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" || true
fi

log "Health check hint"
echo "kubectl port-forward -n ${NAMESPACE} svc/${DEPLOYMENT_NAME} 8080:8080"
echo "curl http://localhost:8080/health"
if [ "${ENABLE_INGRESS}" = "true" ]; then
  echo "Ingress host: ${INGRESS_HOST}"
fi

log "Done"
