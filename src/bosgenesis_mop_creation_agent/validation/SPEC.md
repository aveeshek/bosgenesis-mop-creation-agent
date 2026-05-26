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
- Human MoP section completeness.
- Agent guide contract completeness.
- Target namespace rewrite.
- Blocked resource exclusion.

## Publication gate

Validation failures for secret leakage, production data leakage, blocked executable resources, or missing mandatory artifacts must stop artifact publication.

## Warning behavior

Incomplete evidence, unavailable optional stores, unavailable optional MCPs, and unresolved unknowns may produce warnings when the output remains safe and explicitly labeled.

