# Models Specification

## Intent

`models/` defines future typed contracts for run requests, evidence bundles, reasoning plans, artifacts, validation results, audit events, and configuration views.

## Required model families

- `MoPGenerationRequest`.
- `MoPGenerationResponse`.
- `RunContext`.
- `EvidenceBundle`.
- `ResourceClassification`.
- `ReasoningPlan`.
- `InferenceLabel`.
- `GeneratedArtifact`.
- `ArtifactValidationResult`.
- `AuditEvent`.
- `TraceIds`.
- `EffectiveConfig`.

## Request fields

`MoPGenerationRequest` must include source namespace, target namespace, snapshot selector, mode, include flags, requested artifacts, caller, and optional correlation ID.

## Response fields

`MoPGenerationResponse` must include identifiers, namespaces, status, artifact paths, optional content, counts, warnings, trace IDs, and created timestamp.

## Artifact models

Artifact models must represent:

- human MoP;
- agent-readable guide;
- generated manifest snippets;
- Helm values snippets;
- evidence appendix;
- validation report.

## Design rule

Models must support stable serialization so outputs can be hashed, compared, traced, indexed, and evaluated.

## Safety

Model safe-output methods must redact secrets and omit production data.

