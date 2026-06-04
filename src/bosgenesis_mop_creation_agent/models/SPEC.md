# Models Specification

## Intent

`models/` defines typed contracts for run requests, API/MCP responses, artifact metadata, trace IDs, and future evidence/reasoning models.

## Required model families

- `MoPGenerationRequest`: implemented.
- `MoPGenerationResponse`: implemented.
- `ArtifactMetadata`: implemented.
- `TraceIds`: implemented.
- `McpToolDefinition`: implemented.
- `McpToolResponse`: implemented.
- `RunContext`.
- `EvidenceBundle`.
- `ResourceClassification`.
- `ReasoningPlan`.
- `InferenceLabel`.
- `GeneratedArtifact`.
- `ArtifactValidationResult`.
- `AuditEvent`.
- `EffectiveConfig`.

## Request fields

`MoPGenerationRequest` must include source namespace, target namespace, snapshot selector, mode, include flags, requested artifacts, caller, and optional correlation ID.

## Response fields

`MoPGenerationResponse` must include identifiers, namespaces, status, artifact paths, optional content, inventory/classification counts, warnings, trace IDs, and created timestamp.

## Artifact models

Artifact models must represent:

- human MoP PDF;
- Markdown installation notes;
- standalone machine execution plan YAML;
- generated manifest snippets;
- Helm values snippets;
- evidence appendix;
- validation report.

Artifact path models must support run directory, `artifact.json`, human MoP markdown, PDF, installation notes markdown, and future artifact extensions without breaking response compatibility.

## Design rule

Models must support stable serialization so outputs can be hashed, compared, traced, indexed, and evaluated.

## Safety

Model safe-output methods must redact secrets and omit production data.
