# Observability Specification

## Intent

`observability/` defines structured logging, tracing, metrics, warning taxonomy, and audit contracts.

## Required telemetry

- Structured logs for every phase.
- OpenTelemetry/SigNoz phase spans exported to the configured OTLP collector when SDK/runtime wiring is available.
- Langfuse reasoning metadata traces without raw prompt or response text when endpoint and public/secret keys are configured.
- Structured audit records for MCP calls, Qdrant lookup, reasoning decisions, validation results, rendering, memory, and document decisions.
- Phase latency metrics and warning/error taxonomy in `artifact.json`.
- Redacted non-secret service details for configured Langfuse and SigNoz endpoints.

## Required phases

```text
request_received
memory_read
read_latest_snapshot
enrich_from_mcp
classify_resources
qdrant_reference_lookup
render_artifacts
validate_artifact
llm_reasoning
memory_write
warning_taxonomy
return_response
artifact_preview
artifact_download
artifact_archive
artifact_delete
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

The artifact manifest must include `observability.schema_version`, `trace_ids`, `sinks`, `service_details`, `phase_metrics`, `phase_latency_ms`, `warning_taxonomy`, and `audit_events`. Optional observability sinks must never block generation.

Default lab service details:

- Langfuse endpoint: `http://langfuse-web.bosgenesis.svc.cluster.local:3000`
- SigNoz OTLP endpoint: `http://signoz-otel-collector.signoz.svc.cluster.local:4317`

Langfuse credentials are supplied through Kubernetes Secret keys
`LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`. Missing credentials must report
`enabled_credentials_missing` and must not block generation. SigNoz export uses
OTLP/gRPC port `4317` and must report `enabled_sdk_unavailable` or
`enabled_config_failed` if the exporter cannot be initialized.

## Safety

Logs, traces, metrics, and audit records must be redacted and must not contain secret values or production data.

LLM reasoning telemetry may include candidate counts, parser status, accepted
finding counts, low-confidence rejection counts, model profile name,
correlation ID, and whether LangGraph was used. It must not persist prompt text,
model response text, Qdrant excerpts, manifests, Secret data, credentials, or
production payloads.
