# Models Specification

## Intent

`models/` defines typed contracts for run requests, API/MCP responses, artifact metadata, trace IDs, and future evidence/reasoning models.

## Required model families

- `MoPGenerationRequest`: implemented.
- `NamespaceSwitchRequest`: implemented.
- `MoPGenerationResponse`: implemented.
- `NamespaceStateResponse`: implemented.
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

`NamespaceSwitchRequest` must include namespace and caller. Namespace values
must be valid Kubernetes RFC1123 labels.

## Response fields

`MoPGenerationResponse` must include identifiers, namespaces, status, artifact paths, optional content, inventory/classification counts, warnings, trace IDs, and created timestamp.

Namespace-aware responses must expose `session_context_key` so downstream
memory, LangGraph/LangChain flows, and Codex can bind run context to the active
source namespace.

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
