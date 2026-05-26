# Core Orchestration Specification

## Intent

`core/` coordinates complete MoP generation and refinement runs.

## Responsibilities

- Create run context.
- Validate source namespace, target namespace, generation mode, and v1 scope.
- Read latest snapshot evidence.
- Enrich with Kubernetes and Helm MCP evidence when enabled.
- Merge evidence.
- Classify resources.
- Invoke deterministic and LLM-assisted reasoning.
- Normalize manifests and Helm values.
- Generate human MoP and agent-readable guide.
- Validate artifacts.
- Persist local artifacts and optional stores.
- Return summary and trace identifiers.

## Run identifiers

Every run must include:

- `mop_id`;
- `run_id`;
- `correlation_id`;
- source namespace;
- target namespace;
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
read snapshot
enrich from MCP
merge evidence
classify resources
reason over install order and unknowns
normalize manifests and values
render human MoP
render agent guide
validate artifacts
persist artifacts
return response
```

## Failure policy

- No inventory data fails unless live MCP-only fallback is explicitly enabled.
- Local storage failure fails the request.
- Secret or production-data leakage fails artifact publication.
- Optional store failures continue with warnings.
- External LLM failure in standalone mode fails unless deterministic-only fallback is explicitly enabled.

