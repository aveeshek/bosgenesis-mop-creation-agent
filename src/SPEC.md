# Source Specification

## Intent

`src/` contains the Python implementation of `bosgenesis-mop-creation-agent`.

The source tree must implement a read-only, non-executing, evidence-grounded MoP creation runtime that produces two primary artifacts:

- human-executable MoP PDF rendered from the approved sample-derived template;
- LLM/agent-readable Markdown installation notes.

## Package

The package name is:

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
- `retrieval/`: read-only Qdrant prior-reference lookup for vectorized MoPs and installation notes.
- `reasoning/`: deterministic and LLM-assisted planning.
- `llm/`: external model access boundary.
- `langgraph/`: standalone autonomous reasoning graph and state transitions.
- `langchain/`: model, prompt, and tool abstractions used by standalone reasoning.
- `memory/`: LangMem-shaped in-process memory, Redis short-term memory, PostgreSQL/pgvector episodic memory, and disabled future Qdrant/Letta adapters.
- `documents/`: human MoP PDF and Markdown installation notes rendering.
- `application/`: application-mode schema/topology metadata.
- `validation/`: artifact and plan validation gates.
- `security/`: policy, redaction, and credential handling.
- `observability/`: structured logs, Langfuse, SigNoz/OpenTelemetry, and audit.
- `models/`: stable typed contracts.

## Cross-cutting requirements

Every module must preserve `run_id`, `correlation_id`, source namespace, target namespace, generation mode, caller, and trace context where applicable.

No source module may persist or emit secret values, production data, unredacted credentials, raw table rows, MongoDB documents, Kafka messages, or Redis values.

## Current constraint

Source code is now present and must continue to follow these module contracts. Future implementation should update the relevant `SPEC.md` files before or alongside behavioral changes.
