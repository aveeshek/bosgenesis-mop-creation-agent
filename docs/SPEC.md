# Documentation Specification

## Intent

`docs/` contains product, architecture, design, algorithm, and output contract specifications for the MoP Creation Agent.

The documentation set must preserve the original product context:

- the agent is non-deterministic by nature and may use an LLM to decide next steps when deterministic evidence is insufficient;
- v1 scope is one namespace, namespace-only, Kubernetes and Helm based, and public repositories only;
- the agent produces a sample-format human MoP artifact, a currently valid PDF placeholder, and LLM/agent-readable Markdown installation notes; production-quality PDF rendering is deferred to the PDF renderer phase;
- the Markdown installation notes include a canonical `machine_execution_plan` YAML block, and the same plan is also written as a standalone YAML artifact for downstream agents;
- generated artifacts are retrievable through governed preview, full-file download, generated-folder archive, and housekeeping delete APIs;
- the agent may read existing vectorized MoP/installation-note references from Qdrant for matching components during generation;
- optional Qdrant insertion of generated MoP artifacts is a separate gated admin flow that requires explicit user confirmation, and generation remains read-only;
- Codex integration is through an on-demand MCP server that supports generation, retrieval, configuration inspection, artifact preview, and artifact cleanup;
- standalone mode is triggered through REST, uses LangGraph/LangChain with a configured LLM profile, and uses agentic memory through LangMem and backing stores;
- all actions, tool calls, and reasoning decisions must be traceable in Langfuse, SigNoz/OpenTelemetry, and structured logs;
- future scope includes multi-namespace, cluster-admin add-only scope, custom repositories, Docker image reconstruction hints, and Letta-backed memory.

## Required documents

- Product specification.
- High-level design.
- Low-level design.
- Reasoning algorithm design.
- Human MoP template contract.
- Agent-readable installation notes contract.
- Application-mode schema inference contract.
- Safety and audit contract.
- Sample-derived human MoP template contract.
- Agent-readable Markdown and machine execution plan contract.
- Artifact lifecycle, download/archive, and cleanup contract.
- Deferred production PDF MoP rendering contract.
