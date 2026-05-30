# Classification Specification

## Intent

`classification/` categorizes collected resources before reasoning and rendering.

## Categories

- `helm_managed`
- `raw_k8s`
- `excluded`
- `warning_only`

## Classification rules

A resource is Helm-managed when evidence includes:

- `app.kubernetes.io/managed-by=Helm`;
- `meta.helm.sh/*` annotations;
- release manifest membership;
- release history or chart evidence.

A resource is raw Kubernetes when:

- it is not Helm-managed;
- its kind is supported for raw manifest recreation;
- policy allows it to be emitted as an executable apply step.

A resource is excluded when:

- its kind is blocked;
- it is cluster-scoped in v1;
- it may reveal or mutate credentials/RBAC;
- it cannot be safely recreated from namespace evidence.

## Blocked initial kinds

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
```

## Output

Classification output must include category, reason, evidence references, and warnings.

## Phase 5 implementation contract

- `classify_inventory()` receives a normalized inventory and never performs live Kubernetes,
  Helm, database, or MCP calls.
- Helm-managed detection is evidence based. Initial accepted evidence:
  - `app.kubernetes.io/managed-by=Helm`
  - `meta.helm.sh/release-name`
  - `meta.helm.sh/release-namespace`
  - matching release name from the normalized Helm release inventory
  - membership in a Helm release manifest collected through the Helm Manager MCP
- Raw Kubernetes resources must be namespaced to the source namespace and must be one of:
  - `ConfigMap`
  - `CronJob`
  - `DaemonSet`
  - `Deployment`
  - `Ingress`
  - `Job`
  - `PersistentVolumeClaim`
  - `Service`
  - `StatefulSet`
- Excluded resources are never emitted into executable raw Kubernetes sections.
- Unsupported namespaced resources are `warning_only` manual notes. They may appear in
  classification metadata and warnings, but not in executable raw apply sections.
- Pod runtime artifacts must be summarized as a single warning count instead of one
  warning per Pod.
- The artifact writer must expose classification counts and reasons in `artifact.json`,
  list excluded resources in the human MoP and installation notes, and include only
  `raw_k8s` resources in raw reconstruction inventory and steps.
- The API response must expose `helm_managed_resource_count`, `raw_k8s_resource_count`,
  `excluded_resource_count`, `warning_only_resource_count`, and `classification_summary`.
- A dedicated classification audit endpoint must return resource-level categories and
  evidence references for a generated `mop_id`.
