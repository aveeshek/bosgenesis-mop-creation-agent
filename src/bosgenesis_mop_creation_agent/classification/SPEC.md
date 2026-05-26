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

