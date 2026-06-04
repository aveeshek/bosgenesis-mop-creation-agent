# Core Orchestration Specification

## Intent

`core/` coordinates asynchronous MoP generation runs, artifact lookup, and
local artifact housekeeping.

## Responsibilities

- Create run context.
- Validate source namespace, target namespace, generation mode, and v1 scope.
- Maintain active runtime source namespace initialized from config.
- Support runtime source namespace switching for future requests that do not
  explicitly override `source_namespace`.
- Read latest snapshot evidence.
- Enrich with Kubernetes and Helm MCP evidence when enabled.
- Merge evidence.
- Classify resources.
- Look up read-only Qdrant prior MoP/installation-note references for matching components when enabled.
- Invoke deterministic and LLM-assisted reasoning.
- Normalize manifests and Helm values.
- Generate human MoP PDF and Markdown installation notes.
- Validate artifacts.
- Persist local artifacts and optional stores.
- Return summary and trace identifiers.
- Keep in-memory run state for `accepted`, `generated`, and `failed` runs.
- Keep runtime namespace state and namespace-derived memory/session context key.
- List, preview, download, and archive generated local artifacts.
- Delete one MoP run or all local MoP artifacts with storage-root guardrails.
- Optionally ingest completed redacted MoP artifacts into Qdrant through a config-gated admin flow. This must never be invoked by generation.

## Run identifiers

Every run must include:

- `mop_id`;
- `run_id`;
- `correlation_id`;
- source namespace;
- target namespace;
- namespace-derived `session_context_key`;
- generation mode;
- caller;
- trigger type;
- started timestamp;
- finished timestamp;
- trace identifiers.

## Orchestration sequence

```text
validate request
create run context
start trace
return accepted response
continue background generation
read snapshot
enrich from MCP
merge evidence
classify resources
lookup qdrant prior references
reason over install order and unknowns when enabled
normalize manifests and values
render sample-format human MoP markdown and paginated PDF
render Markdown installation notes and machine execution plan YAML
validate artifacts
persist artifacts
store generated response
```

The default source namespace comes from `agent.source_namespace`. When the
runtime active namespace is switched, future requests without explicit
`source_namespace` must use that active namespace. Requests that include
`source_namespace` are per-run overrides and must not mutate the runtime active
namespace.

Optional Qdrant ingestion sequence:

```text
validate ingestion config enabled
require confirm=true
resolve mop_id under artifact storage root
build redacted reference payloads from completed artifacts
upsert reference payloads to Qdrant
return point count and status
```

## Failure policy

- No inventory data may continue with warnings when governed MCP live fallback or
  empty artifact generation remains safe.
- Local storage failure fails the request.
- Secret or production-data leakage fails artifact publication.
- Optional store failures continue with warnings.
- Qdrant disabled, unavailable, or no-match conditions continue with warnings and no prior references.
- Optional LLM repair/suggestion failure continues with warnings and deterministic output.
- Artifact download/archive/delete operations must deny paths outside the local storage root.

## Artifact lifecycle

`core/` owns local artifact path resolution and must:

- resolve all paths under `agent.local_storage_path`;
- deny path traversal and absolute-path escape;
- expose capped preview for approved text artifacts;
- expose non-truncated download for approved text artifacts;
- create zip archives for approved artifact directories such as `generated/`;
- delete one run directory by `mop_id`;
- delete all run directories only when `confirm=true`.
