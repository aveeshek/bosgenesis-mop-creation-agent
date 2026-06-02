# Reconstruction Specification

## Intent

`reconstruction/` converts classified platform inventory into target-namespace
reconstruction artifacts and copyable commands.

## Phase 6 contract

- Only `raw_k8s` classified resources are written as raw Kubernetes manifests.
- Helm-managed resources are reconstructed through Helm release commands and values files.
- Kubernetes Secrets, blocked resources, warning-only runtime resources, and
  cluster-scoped resources must not be written as executable raw manifests.
- Raw manifest generation must rewrite `metadata.namespace` to the target namespace.
- Raw manifest generation must remove runtime metadata and status fields.
- Helm values files must be redacted before writing to local storage.
- Command builders must emit:
  - dry-run commands;
  - apply/install commands;
  - validation commands;
  - rollback commands.
- Generated command text may still require human review where chart references or
  source manifests are incomplete, but it must be concrete enough to inspect and
  run in dry-run mode after human fixes.
