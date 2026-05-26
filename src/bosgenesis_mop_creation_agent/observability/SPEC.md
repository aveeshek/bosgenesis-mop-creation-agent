# Observability Specification

## Intent

`observability/` defines structured logging, tracing, metrics, and audit contracts.

## Required telemetry

- Structured logs for every phase.
- OpenTelemetry traces for SigNoz.
- Langfuse traces for prompts, model calls, and generation decisions.
- Audit records for tool calls, reasoning decisions, validation results, and document decisions.

## Required phases

```text
request_received
read_latest_snapshot
enrich_from_mcp
classify_resources
llm_reasoning_started
llm_reasoning_completed
normalize_manifests
render_mop
agent_guide_rendered
validate_artifact
persist_mop
return_response
```

## Trace identifiers

Every emitted event must carry:

- `mop_id` when available;
- `run_id`;
- `correlation_id`;
- source namespace;
- target namespace;
- generation mode;
- caller;
- phase;
- status;
- latency;
- error details when present.

## Safety

Logs, traces, metrics, and audit records must be redacted and must not contain secret values or production data.

