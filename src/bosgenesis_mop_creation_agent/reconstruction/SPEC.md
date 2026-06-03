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

## Phase 8 interaction

The reconstruction plan is the source for the Markdown `machine_execution_plan`.
Each raw manifest and Helm release plan must expose enough structured data for
the renderer to produce:

- phase assignment;
- dry-run, apply/install, validation, and rollback command kinds;
- expected outcomes;
- evidence references;
- required human inputs for missing chart references or excluded secret material.

Generated manifests under `generated/` are intended to be downloadable one file
at a time or as a zip archive through the artifact APIs.
