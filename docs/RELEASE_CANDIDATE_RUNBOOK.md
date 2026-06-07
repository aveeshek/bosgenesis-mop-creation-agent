# Phase 15 Release Candidate Runbook

## Purpose

This runbook describes how to validate `bosgenesis-mop-creation-agent` as an
end-to-end release candidate.

Phase 15 does not make the agent an executor. The agent generates artifacts;
operators or downstream agents review and execute generated commands.

## Release Candidate Identity

Helm values include:

```yaml
release:
  values_schema_version: phase15.rc.v1
  release_candidate: phase15-rc1
  app_version: "0.1.0"
  docs_version: phase15
```

Verify from the deployed API:

```powershell
Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/health |
  Select-Object status, version, release_candidate, values_schema_version
```

## Prerequisites

- Agent pod is deployed and ready.
- Ingress host resolves to the lab ingress controller.
- PostgreSQL inventory DSN is configured and redacted in `/config/effective`.
- ClickHouse inventory settings are configured when used.
- Qdrant prior-reference lookup endpoint is reachable when enabled.
- Redis and PostgreSQL/pgvector memory are available when memory is enabled.
- Langfuse keys are configured if reasoning traces should appear in Langfuse.
- SigNoz OTLP endpoint is configured for OpenTelemetry spans.
- Existing MCP dependencies are reachable:
  - Kubernetes Inspector MCP;
  - Helm Manager MCP;
  - Data Ingestion Agent MCP.

## Pre-Flight Checks

```powershell
Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/health |
  ConvertTo-Json -Depth 10

Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/config/effective |
  ConvertTo-Json -Depth 30

Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/mcp/tools |
  ConvertTo-Json -Depth 20
```

Confirm:

- health status is `ok`;
- active source namespace is expected;
- credentials are redacted;
- `observability.sinks` can become `langfuse: enabled` and `signoz: enabled`
  after a generation run;
- `memory.enabled` reflects the intended lab setting;
- Qdrant retrieval is read-only.

## Platform-Only RC Generation

Generate a platform-only MoP:

```powershell
$body = @{
  target_namespace = "bosgenesis-platform-rc"
  mode = "platform-only"
  include_helm = $true
  include_raw_k8s = $true
  include_validation_steps = $true
  include_rollback_steps = $true
  caller = "phase15-operator"
  correlation_id = "phase15-platform-only-rc"
} | ConvertTo-Json

$run = Invoke-RestMethod `
  -Method Post `
  -Uri "http://mop-creation-agent.bosgenesis.local/mop-creation/generate" `
  -ContentType "application/json" `
  -Body $body
```

Poll until `generated`:

```powershell
$mopId = $run.mop_id
do {
  $run = Invoke-RestMethod "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId"
  $run | Select-Object status, resource_count, helm_release_count, warning_count, memory_status, qdrant_lookup_status
  Start-Sleep -Seconds 5
} while ($run.status -in @("accepted", "running"))
```

Acceptance:

- `status` is `generated`;
- `resource_count` is greater than zero;
- Helm and raw Kubernetes counts are populated;
- `inventory_source` includes snapshot or MCP evidence;
- artifacts paths are present;
- warnings are explainable and non-blocking.

## Application-Mode RC Smoke Test

Application mode remains deferred/backlog for real schema/topic generation.
Phase 15 still smoke-tests the request path to confirm it is safe and explicit.

```powershell
$body = @{
  target_namespace = "bosgenesis-application-rc"
  mode = "application"
  include_helm = $true
  include_raw_k8s = $true
  include_validation_steps = $true
  include_rollback_steps = $true
  include_application_schema = $true
  caller = "phase15-operator"
  correlation_id = "phase15-application-mode-rc"
} | ConvertTo-Json

$run = Invoke-RestMethod `
  -Method Post `
  -Uri "http://mop-creation-agent.bosgenesis.local/mop-creation/generate" `
  -ContentType "application/json" `
  -Body $body
```

Acceptance:

- run completes with platform artifacts;
- machine plan includes `apply_application_metadata`;
- application metadata steps require human input/review but do not mutate the target;
- no executable database schema, topic, Redis value, or production-data command
  is silently created by the LLM;
- output clearly labels application mode as deferred/human-review.

## Human Operator Review

Download the PDF and installation notes through the artifact API.

Human operator checklist:

- Cover page and executive summary identify source/target namespaces.
- Namespace analytical summary and inventory counts are plausible.
- Actual execution steps are ordered and copy-pasteable.
- Helm commands include dry-run and apply variants.
- Raw Kubernetes commands reference generated manifests and target namespace.
- Validation section contains human-readable validation commands.
- Go/no-go and rollback controls are clear.
- Appendix A resource tables are readable.
- Secrets are placeholders only.
- Application-mode placeholders, if present, are not executable schema/data
  mutation commands.

## LLM Consumption Review

Ask another LLM or Codex session to read the installation notes and answer:

```text
Explain the execution order. Which steps mutate the target namespace? Which
steps require human approval? Which generated files are required before running
the commands? What evidence or inference label supports each phase?
```

Acceptance:

- downstream LLM identifies the dependency order from `machine_execution_plan`;
- downstream LLM can distinguish dry-run, apply, validate, and rollback
  commands;
- downstream LLM does not treat suggestions as observed facts;
- downstream LLM flags required human inputs.

## Safe Dry-Run Execution

Use a non-production target namespace.

Recommended namespace pattern:

```text
bosgenesis-rc-dryrun-<date>
```

Dry-run only:

1. Download generated manifests zip with `prefix=generated/`.
2. Download values files as needed.
3. Execute only commands marked `dry_run` or validation commands that do not
   mutate the cluster.
4. Do not execute apply/delete/upgrade commands unless an operator has approved
   the test.

Acceptance:

- dry-run commands parse successfully;
- generated manifests contain only the target namespace;
- blocked resources and Secrets are not present;
- validation commands are namespace-explicit.

## Observability Verification

From `artifact.json`:

```powershell
$artifact.observability.sinks
$artifact.observability.trace_ids
$artifact.observability.warning_taxonomy
$artifact.observability.phase_latency_ms
```

Acceptance:

- `langfuse` is `enabled` when credentials are configured;
- `signoz` is `enabled`;
- audit event count is greater than zero;
- phase latency metrics are present;
- Qdrant lookup, MCP calls, validation, rendering, and memory read/write events
  appear in audit events.

## Failure Handling

If generation fails:

1. Check `GET /mop-creation/{mop_id}` for status and warnings.
2. Download `artifact.json` if present.
3. Inspect `observability.audit_events`.
4. Check pod logs by `correlation_id`.
5. Verify MCP dependency health.
6. Verify inventory DSNs and credentials.
7. Retry with a new target namespace and correlation ID.

## Release Candidate Exit Criteria

- Platform-only generation succeeds.
- Application-mode smoke test completes safely with human-review placeholders.
- Human operator accepts PDF usability.
- Another LLM can consume installation notes and explain execution order.
- Safe target dry-run commands are manually reviewed and pass where expected.
- Langfuse and SigNoz traces are visible when configured.
- Generated artifacts contain no secrets or production data.
- Validation gates pass:
  - Ruff;
  - pytest;
  - pytest XML report;
  - coverage XML;
  - coverage HTML.
