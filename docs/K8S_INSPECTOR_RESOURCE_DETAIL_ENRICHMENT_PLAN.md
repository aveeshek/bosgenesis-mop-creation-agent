# K8s Inspector MCP Resource Detail Enrichment Plan

## Purpose

Add safe, namespace-scoped full resource detail reads to `bosgenesis-k8s-inspector-mcp` so `bosgenesis-mop-creation-agent` can generate complete raw Kubernetes manifests during Phase 6 reconstruction.

The MoP agent currently receives shallow resource inventory for many raw Kubernetes resources. As a result, generated manifests may be minimal and marked with warnings such as:

```text
source_manifest_missing_minimal_manifest_generated
source_spec_missing_manifest_requires_human_completion
```

This plan adds a safe detail-read capability to the Kubernetes Inspector MCP. The MoP agent will later consume it as enrichment evidence.

## Phase A: Add Safe Detail Read Tool

Add one generic MCP tool:

```text
k8s_get_resource
```

### Tool Input

```json
{
  "namespace": "bosgenesis",
  "kind": "Deployment",
  "name": "some-resource",
  "actor": "bosgenesis-mop-creation-agent",
  "correlation_id": "optional-correlation-id"
}
```

### Supported Kinds

Allow only namespace-scoped, reconstruction-safe resource kinds:

```text
ConfigMap
Service
Deployment
StatefulSet
DaemonSet
Job
CronJob
PersistentVolumeClaim
Ingress
```

### Always Blocked Kinds

```text
Secret
ServiceAccount
Role
RoleBinding
ClusterRole
ClusterRoleBinding
Namespace
Node
PersistentVolume
CustomResourceDefinition
StorageClass
IngressClass
PriorityClass
MutatingWebhookConfiguration
ValidatingWebhookConfiguration
```

## Phase B: Safety Rules

Before any Kubernetes API call, enforce:

- Namespace must equal the configured namespace, currently `bosgenesis`.
- Kind must be in the allowed list.
- Name is required and non-empty.
- Cluster-scoped resources are denied.
- Secrets are denied.
- Tool is read-only.
- No `pods/exec`, `pods/attach`, or port-forward behavior.
- No raw `kubectl` shell execution.
- Every call must generate an audit record.

## Phase C: Audit Contract

Every `k8s_get_resource` call must emit an audit record with:

```text
timestamp
actor
operation=k8s_get_resource
namespace
kind
name
dry_run=false
correlation_id
decision=allowed|denied
result=success|failure
error_message, when applicable
```

Denials must also be audited.

## Phase D: Kubernetes Fetch Behavior

Implementation behavior:

1. Validate namespace, kind, and name.
2. Resolve the allowed kind to the correct Kubernetes API client.
3. Fetch exactly one namespaced object.
4. Return the full Kubernetes object as a JSON-compatible dictionary.
5. Do not strip runtime metadata in the inspector MCP.
6. Do not redact or mutate the returned allowed resource object.

The MoP agent owns manifest normalization, target namespace rewrite, runtime metadata removal, and values redaction.

### Response Shape

```json
{
  "status": "ok",
  "namespace": "bosgenesis",
  "kind": "Deployment",
  "name": "some-resource",
  "resource": {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {},
    "spec": {},
    "status": {}
  }
}
```

### Not Found Shape

Use a controlled failure response or MCP error, consistent with existing MCP patterns:

```json
{
  "status": "not_found",
  "namespace": "bosgenesis",
  "kind": "Deployment",
  "name": "missing-resource",
  "error": "resource_not_found"
}
```

## Phase E: Tests In `bosgenesis-k8s-inspector-mcp`

Add tests for:

- Allowed `Deployment` returns full object.
- Allowed `Service` returns full object.
- Allowed `ConfigMap` returns full object.
- Allowed `PersistentVolumeClaim` returns full object.
- Blocked `Secret` is denied.
- Blocked `ClusterRole` is denied.
- Blocked `Namespace` is denied.
- Wrong namespace is denied.
- Missing name is denied.
- Unknown kind is denied.
- Not found returns controlled error.
- Audit record is emitted for success.
- Audit record is emitted for denial.
- Audit record is emitted for not found.

## Phase F: Update OpenAPI / MCP Contract

Expose the new tool in the MCP tool list and REST/OpenAPI surface if the MCP server mirrors MCP tools as REST endpoints.

Recommended tool description:

```text
Read one allowed namespaced Kubernetes resource as full JSON for reconstruction evidence. Secrets and cluster-scoped resources are denied.
```

Recommended input schema:

```json
{
  "type": "object",
  "properties": {
    "namespace": {
      "type": "string"
    },
    "kind": {
      "type": "string",
      "enum": [
        "ConfigMap",
        "Service",
        "Deployment",
        "StatefulSet",
        "DaemonSet",
        "Job",
        "CronJob",
        "PersistentVolumeClaim",
        "Ingress"
      ]
    },
    "name": {
      "type": "string"
    },
    "actor": {
      "type": "string"
    },
    "correlation_id": {
      "type": "string"
    }
  },
  "required": ["namespace", "kind", "name"],
  "additionalProperties": false
}
```

## Phase G: MoP Agent Follow-Up

After `k8s_get_resource` is deployed in `bosgenesis-k8s-inspector-mcp`, update `bosgenesis-mop-creation-agent`:

1. Add `k8s_get_resource` to allowed Kubernetes MCP tools.
2. After list calls, fetch detail for raw-eligible resource kinds:
   - `ConfigMap`
   - `Service`
   - `Deployment`
   - `StatefulSet`
   - `DaemonSet`
   - `Job`
   - `CronJob`
   - `PersistentVolumeClaim`
   - `Ingress`
3. Store returned `resource` object in `InventoryResource.normalized_payload`.
4. Regenerate Phase 6 artifacts.
5. Confirm reconstruction warnings drop sharply.

## Phase 6.1 Deterministic Enrichment And Optional Preview

The MoP agent consumes `k8s_get_resource` deterministically whenever the K8s
Inspector MCP advertises the tool. This is not an optional reconstruction path.
If the tool is unavailable, the agent keeps the previous list-only enrichment
behavior and emits a warning instead of failing generation.

The enrichable kinds remain configurable:

```yaml
mcp:
  k8s_inspector:
    detail_enrichment_kinds:
      - ConfigMap
      - Service
      - Deployment
      - StatefulSet
      - DaemonSet
      - Job
      - CronJob
      - PersistentVolumeClaim
      - Ingress
```

Phase 6.1 also adds controlled artifact preview as the optional inspection flow, plus full artifact download and generated-folder archive retrieval for cases where the caller needs the complete output:

```text
GET /mop-creation/{mop_id}/artifacts
GET /mop-creation/{mop_id}/artifacts/preview?path=generated/<file>.yaml
GET /mop-creation/{mop_id}/artifacts/download?path=generated/<file>.yaml
GET /mop-creation/{mop_id}/artifacts/archive?prefix=generated/
```

Preview is bounded by configuration:

```yaml
features:
  artifact_preview:
    enabled: true
    max_bytes: 262144
    allowed_extensions:
      - .json
      - .md
      - .yaml
      - .yml
```

Preview, download, and archive must never read outside the selected `mop_id` artifact directory. Preview remains size-bounded; download and archive return full allowed artifact content.

## Success Criteria

The integration is successful when:

- MoP generation still never calls raw `kubectl`.
- No Secrets are read or returned.
- No cluster-scoped resources are read or returned.
- Generated raw manifests contain real `spec` fields.
- Generated raw manifests use only the target namespace.
- Runtime metadata is removed by the MoP agent.
- Helm-managed resources remain classified as Helm-managed.
- Raw Kubernetes resources produce meaningful dry-run commands.
- Reconstruction warnings drop from the current high count to only genuinely incomplete or unsupported resources.

## Expected Phase 6 Improvement

Before enrichment:

```text
raw_manifest:<kind>/<name>:source_manifest_missing_minimal_manifest_generated
raw_manifest:<kind>/<name>:source_spec_missing_manifest_requires_human_completion
```

After enrichment:

```text
generated/deployment-<name>.yaml includes spec.template
generated/service-<name>.yaml includes ports/selectors
generated/ingress-<name>.yaml includes rules
generated/pvc-<name>.yaml includes storage requests
```

The generated MoP and installation notes should then be suitable for manual server-side dry-run validation.
