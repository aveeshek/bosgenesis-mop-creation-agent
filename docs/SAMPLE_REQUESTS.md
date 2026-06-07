# Sample API Requests

## Purpose

This document provides copy-pasteable Phase 15 release-candidate API requests.

Replace namespaces before using in a shared lab.

## Health

```powershell
Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/health |
  ConvertTo-Json -Depth 10
```

Expected fields include `status`, `version`, `release_candidate`,
`values_schema_version`, `source_namespace`, and `session_context_key`.

## Effective Config

```powershell
Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/config/effective |
  ConvertTo-Json -Depth 20
```

Secrets must be redacted. Langfuse keys, PostgreSQL DSNs, pgvector DSNs,
ClickHouse passwords, and any key/token/password fields must not appear in
plaintext.

## Platform-Only Generation

```powershell
$body = @{
  target_namespace = "bosgenesis-platform-rc"
  mode = "platform-only"
  include_helm = $true
  include_raw_k8s = $true
  include_validation_steps = $true
  include_rollback_steps = $true
  include_application_schema = $false
  caller = "phase15-operator"
  correlation_id = "phase15-platform-only-rc"
} | ConvertTo-Json

$run = Invoke-RestMethod `
  -Method Post `
  -Uri "http://mop-creation-agent.bosgenesis.local/mop-creation/generate" `
  -ContentType "application/json" `
  -Body $body

$run | ConvertTo-Json -Depth 20
```

Poll:

```powershell
$mopId = "<mop-id>"
do {
  $run = Invoke-RestMethod "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId"
  $run | Select-Object status, resource_count, helm_release_count, warning_count, memory_status, qdrant_lookup_status
  Start-Sleep -Seconds 5
} while ($run.status -in @("accepted", "running"))
```

## Application-Mode RC Smoke Test

Application mode is a deferred/backlog metadata contract in this release
candidate. This smoke test verifies that selecting `application` does not copy
data, does not execute schema creation, and produces human-review placeholders
where application metadata would be added in a future phase.

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

Invoke-RestMethod `
  -Method Post `
  -Uri "http://mop-creation-agent.bosgenesis.local/mop-creation/generate" `
  -ContentType "application/json" `
  -Body $body |
  ConvertTo-Json -Depth 20
```

Expected application-mode behavior in this RC:

- platform evidence and platform artifacts are still generated;
- machine execution plan includes `apply_application_metadata`;
- application metadata step requires human input/review but does not mutate the target;
- no database rows, documents, Redis values, Kafka messages, or production data
  are copied;
- warnings or notes may indicate application mode is deferred.

## Artifact Index

```powershell
$mopId = "<mop-id>"
Invoke-RestMethod "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts" |
  ConvertTo-Json -Depth 20
```

## Download Artifact Manifest

```powershell
$mopId = "<mop-id>"
$artifact = (Invoke-WebRequest `
  "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts/download?path=artifact.json").Content |
  ConvertFrom-Json

$artifact.observability.sinks
$artifact.machine_execution_plan.machine_execution_plan.phases.phase_id
```

## Download Installation Notes

```powershell
$mopId = "<mop-id>"
Invoke-WebRequest `
  "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts/download?path=<installation-notes-file>" `
  -OutFile ".\installation-notes.md"
```

Use the artifact index to find the relative installation-notes path.

## Download PDF MoP

```powershell
$mopId = "<mop-id>"
Invoke-WebRequest `
  "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts/download?path=<pdf-file>" `
  -OutFile ".\human-mop.pdf"
```

Use the artifact index to find the relative PDF path.

## Download Generated Folder Zip

```powershell
$mopId = "<mop-id>"
Invoke-WebRequest `
  "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts/archive?prefix=generated/" `
  -OutFile ".\generated-manifests.zip"
```

## Qdrant Ingestion, Explicit Only

Generation never writes to Qdrant. To ingest a completed redacted MoP bundle
for future reference lookup:

```powershell
$body = @{
  mop_id = "<mop-id>"
  caller = "phase15-operator"
  confirm = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://mop-creation-agent.bosgenesis.local/references/qdrant/ingest-mop" `
  -ContentType "application/json" `
  -Body $body |
  ConvertTo-Json -Depth 20
```

## Cleanup

Delete one run:

```powershell
Invoke-RestMethod `
  -Method Delete `
  -Uri "http://mop-creation-agent.bosgenesis.local/mop-creation/<mop-id>" |
  ConvertTo-Json -Depth 20
```

Delete all generated runs:

```powershell
Invoke-RestMethod `
  -Method Delete `
  -Uri "http://mop-creation-agent.bosgenesis.local/mop-creation?confirm=true" |
  ConvertTo-Json -Depth 20
```
