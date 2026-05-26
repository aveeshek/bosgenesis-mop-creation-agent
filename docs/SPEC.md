# Documentation Specification

## Intent

`docs/` contains product, architecture, design, algorithm, and output contract specifications for the MoP Creation Agent.

The documentation set must preserve the original product context:

- the agent is non-deterministic by nature and may use an LLM to decide next steps when deterministic evidence is insufficient;
- v1 scope is one namespace, namespace-only, Kubernetes and Helm based, and public repositories only;
- the agent produces both a human-executable MoP PDF rendered from the approved sample MoP template and LLM/agent-readable Markdown installation notes;
- the agent may read existing vectorized MoP/installation-note references from Qdrant for matching components, but Qdrant ingestion is owned by a separate agent;
- Codex integration is through an on-demand MCP server that supports iterative refinement;
- standalone mode is triggered through REST, uses LangGraph/LangChain with GPT-4.1 mini or equivalent configured model, and uses agentic memory through LangMem and backing stores;
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
- Sample-derived PDF MoP rendering contract.
