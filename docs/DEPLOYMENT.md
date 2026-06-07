# Deployment Guide

## Purpose

This guide describes how to build, deploy, upgrade, and verify
`bosgenesis-mop-creation-agent` in the BOS Genesis lab.

## Build And Deploy

Default deployment:

```bash
IMAGE_REPOSITORY=bosgenesis-mop-creation-agent \
IMAGE_TAG=0.0.1 \
./playbook/deploy.sh
```

The deploy script:

- builds the Docker image unless `SKIP_BUILD=true`;
- saves and transfers the image tar to the configured remote host;
- imports the image into containerd;
- deploys or upgrades the Helm release;
- uses `charts/bosgenesis-mop-creation-agent/values.credentials.yaml` when it
  exists;
- waits for rollout;
- prints service, ingress, and health-check hints.

## Important Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `IMAGE_REPOSITORY` | `bosgenesis-mop-creation-agent` | Image repository/name to build and deploy. |
| `IMAGE_TAG` | `0.0.1` | Image tag to build and deploy. |
| `NAMESPACE` | `bosgenesis` | Kubernetes namespace for the agent deployment. |
| `HELM_RELEASE` | `bosgenesis-mop-creation-agent` | Helm release name. |
| `HELM_CHART` | `charts/bosgenesis-mop-creation-agent` | Chart path. |
| `HELM_VALUES_FILE` | auto-detect credentials file | Optional secure values file. |
| `INGRESS_HOST` | `mop-creation-agent.bosgenesis.local` | Ingress host. |
| `LANGFUSE_ENABLED` | `true` | Enables Langfuse sink config. |
| `SIGNOZ_ENABLED` | `true` | Enables SigNoz/OpenTelemetry sink config. |
| `QDRANT_RETRIEVAL_ENABLED` | `true` | Enables Qdrant reference lookup. |
| `SOURCE_NAMESPACE` | `bosgenesis` | Default source namespace. |
| `LOG_LEVEL` | `INFO` | Structured log level. |

## Versioned Helm Values

The chart values include release metadata:

```yaml
release:
  values_schema_version: phase15.rc.v1
  release_candidate: phase15-rc1
  app_version: "0.1.0"
  docs_version: phase15
```

Verify after deploy:

```powershell
Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/health |
  Select-Object version, release_candidate, values_schema_version
```

## Credentials

Use the ignored credentials file or pass an external secure values file:

```text
charts/bosgenesis-mop-creation-agent/values.credentials.yaml
```

See `docs/CREDENTIALS.md` for PostgreSQL, pgvector, ClickHouse, Redis, Qdrant,
Langfuse, SigNoz, MCP, and LLM configuration.

Never put real credentials in tracked `values.yaml`.

## Rollout Verification

```bash
kubectl rollout status deployment/bosgenesis-mop-creation-agent -n bosgenesis
kubectl get pod -n bosgenesis -l app.kubernetes.io/name=bosgenesis-mop-creation-agent -o wide
kubectl get svc bosgenesis-mop-creation-agent -n bosgenesis
kubectl get ingress bosgenesis-mop-creation-agent -n bosgenesis
```

API checks:

```powershell
Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/health |
  ConvertTo-Json -Depth 10

Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/config/effective |
  ConvertTo-Json -Depth 30
```

## Smoke Test

Generate a platform-only run:

```powershell
$body = @{
  target_namespace = "bosgenesis-deploy-smoke"
  mode = "platform-only"
  caller = "deployment-smoke"
  correlation_id = "deployment-smoke"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://mop-creation-agent.bosgenesis.local/mop-creation/generate" `
  -ContentType "application/json" `
  -Body $body |
  ConvertTo-Json -Depth 20
```

Poll until generated:

```powershell
Invoke-RestMethod "http://mop-creation-agent.bosgenesis.local/mop-creation/<mop-id>" |
  ConvertTo-Json -Depth 20
```

## Rollback

Use Helm rollback when the release history contains a known-good revision:

```bash
helm history bosgenesis-mop-creation-agent -n bosgenesis
helm rollback bosgenesis-mop-creation-agent <revision> -n bosgenesis
```

Uninstall:

```bash
./playbook/uninstaller.sh
```

The PVC may retain generated artifacts depending on uninstaller settings and
cluster storage policy. Delete generated MoP artifacts through the API before
uninstalling when the PVC must be clean.
