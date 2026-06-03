# Validation Specification

## Intent

`validation/` checks generated plans, manifests, values, and documents before delivery.

## Required checks

- Namespace scope compliance.
- Single-namespace v1 compliance.
- Public-repository-only v1 compliance.
- Secret redaction.
- No production data export.
- Evidence citation coverage.
- Inference labeling.
- Command ordering.
- Idempotency notes.
- Dry-run guidance.
- Rollback notes.
- Unknowns explicitly listed.
- Platform-only versus application-mode boundary compliance.
- Sample-derived human MoP PDF section completeness.
- Markdown installation notes contract completeness.
- Machine execution plan YAML contract completeness.
- No YAML aliases/anchors in machine-readable plan output.
- Target namespace rewrite.
- Blocked resource exclusion.
- Artifact path containment for preview, download, archive, and delete.
- Archive output contains only approved artifact extensions.

## Publication gate

Validation failures for secret leakage, production data leakage, blocked executable resources, or missing mandatory artifacts must stop artifact publication.

Artifact lifecycle validation failures for path traversal or unsupported
extensions must deny the API/MCP request without touching the filesystem outside
the configured artifact storage root.

## Warning behavior

Incomplete evidence, unavailable optional stores, unavailable optional MCPs, and unresolved unknowns may produce warnings when the output remains safe and explicitly labeled.
