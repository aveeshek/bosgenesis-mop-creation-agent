# Technology Stack Specification

## Runtime

- Python service runtime in future implementation.
- FastAPI for REST trigger and service endpoints.
- Streamable HTTP MCP endpoint for Codex integration.
- LangGraph for standalone reasoning workflow graphs and state transitions.
- LangChain for model, prompt, and tool abstractions where useful.
- LangMem for agentic memory.

## LLM

- Initial standalone model target: GPT-4.1 mini.
- Codex-integrated mode delegates iterative reasoning to Codex through MCP calls.

## MCP dependencies

- Kubernetes Inspector MCP.
- Helm Manager MCP.
- K8s Data Ingestion Agent MCP.
- Future data-source MCPs for PostgreSQL, ClickHouse, Redis, MongoDB, Kafka, and similar components.

## Observability

- Structured JSON logs.
- OpenTelemetry traces and metrics.
- SigNoz for runtime observability.
- Langfuse for LLM reasoning traces, prompts, generations, and evaluations.

## Storage and memory

- Redis for short-term state and run coordination.
- PostgreSQL for run metadata, artifacts, and audit records.
- MongoDB for flexible evidence bundles and episodic records.
- ClickHouse for analytical event history.
- LangMem as the memory abstraction layer.
