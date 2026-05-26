# Source Specification

## Intent

`src/` will contain the future Python implementation of `bosgenesis-mop-creation-agent`.

The source tree must implement a read-only, non-executing, evidence-grounded MoP creation runtime that produces two primary artifacts:

- human-executable MoP Markdown;
- LLM/agent-readable installation guide Markdown.

## Package

The future package name is:

```text
bosgenesis_mop_creation_agent
```

## V1 boundaries

- One source namespace only.
- Namespace-only Kubernetes scope.
- Kubernetes and Helm based reconstruction.
- Public repositories only.
- No production data population.
- No execution of generated commands.
- No raw `kubectl`, raw `helm`, or datastore CLIs from the agent runtime when an approved MCP/evidence boundary exists.

## Module groups

- `api/`: REST and MCP surfaces.
- `entrypoints/`: process startup modes.
- `core/`: orchestration and run lifecycle.
- `mcp_clients/`: governed upstream MCP access.
- `collectors/`: evidence collection.
- `evidence/`: normalized evidence bundles and citations.
- `reasoning/`: deterministic and LLM-assisted planning.
- `llm/`: external model access boundary.
- `langchain/`: standalone autonomous reasoning workflow.
- `memory/`: LangMem and backing memory stores.
- `documents/`: human MoP and agent-readable guide rendering.
- `application/`: application-mode schema/topology metadata.
- `validation/`: artifact and plan validation gates.
- `security/`: policy, redaction, and credential handling.
- `observability/`: structured logs, Langfuse, SigNoz/OpenTelemetry, and audit.
- `models/`: stable typed contracts.

## Cross-cutting requirements

Every module must preserve `run_id`, `correlation_id`, source namespace, target namespace, generation mode, caller, and trace context where applicable.

No source module may persist or emit secret values, production data, unredacted credentials, raw table rows, MongoDB documents, Kafka messages, or Redis values.

## Current constraint

No source code is present in this scaffold. Future implementation should be added only after these module contracts are reviewed.

