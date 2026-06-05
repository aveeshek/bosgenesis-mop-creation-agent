# Credentials and Service Configuration Runbook

## Purpose

This runbook explains how to add or update runtime credentials and service endpoints for `bosgenesis-mop-creation-agent`.

Credentials must be supplied through the ignored Helm credentials values file and Kubernetes Secret. Non-secret service endpoints can stay in `values.yaml` or be overridden during deploy.

Never commit real passwords, API keys, DSNs, Langfuse keys, tokens, or connection strings.

## Files

| File | Purpose | Git status |
|---|---|---|
| `charts/bosgenesis-mop-creation-agent/values.yaml` | Non-secret defaults such as service endpoints, enabled flags, ports, collections, and table names. | Tracked |
| `charts/bosgenesis-mop-creation-agent/values.credentials.yaml` | Operator-maintained secrets and sensitive DSNs. `playbook/deploy.sh` uses this file automatically when present. | Ignored |
| `charts/bosgenesis-mop-creation-agent/templates/secret.yaml` | Maps `values.credentials.yaml` entries into Kubernetes Secret environment variables. | Tracked |

The repository `.gitignore` excludes `values.credentials.yaml`, so real credentials should be placed only there or in a separately managed secure values file passed with `HELM_VALUES_FILE`.

## Credential Update Flow

1. Edit `charts/bosgenesis-mop-creation-agent/values.credentials.yaml`.
2. Keep `secret.create: true` when Helm should create or update the Kubernetes Secret.
3. Rebuild and redeploy through `playbook/deploy.sh`.
4. Verify redacted effective config through `GET /config/effective`.
5. Trigger a generation run and inspect `artifact.json -> observability.sinks`, `memory_status`, and source status fields.

Example deploy:

```bash
IMAGE_REPOSITORY=bosgenesis-mop-creation-agent \
IMAGE_TAG=0.0.1 \
./playbook/deploy.sh
```

To use a different private values file:

```bash
HELM_VALUES_FILE=/secure/path/mop-agent.credentials.yaml ./playbook/deploy.sh
```

## Credentials Values Template

Use placeholder values in documentation and real values only in the ignored credentials file:

```yaml
inventoryConfig:
  postgresEnabled: "true"
  postgresSchema: "k8s_ingestion"
  clickhouseEnabled: "true"
  clickhouseHost: "clickhouse.bosgenesis.svc.cluster.local"
  clickhousePort: "8123"
  clickhouseUser: "bosgenesis"
  clickhouseDatabase: "bosgenesis_k8s_ingestion"

secret:
  create: true
  name: bosgenesis-mop-creation-agent-secret
  postgresDsn: "postgresql://<user>:<password>@postgresql.bosgenesis.svc.cluster.local:5432/<database>"
  memoryPgvectorDsn: "postgresql://<user>:<password>@postgresql.bosgenesis.svc.cluster.local:5432/<database>"
  clickhousePassword: "<clickhouse-password>"
  langfusePublicKey: "<langfuse-public-key>"
  langfuseSecretKey: "<langfuse-secret-key>"
```

## Component Mapping

| Component | Sensitive values | Non-secret values | Runtime setting or env |
|---|---|---|---|
| PostgreSQL inventory reader | `secret.postgresDsn` | `inventoryConfig.postgresEnabled`, `inventoryConfig.postgresSchema` | `POSTGRES_DSN`, `POSTGRES_ENABLED`, `POSTGRES_SCHEMA` |
| PostgreSQL/pgvector episodic memory | `secret.memoryPgvectorDsn` | `config.memory.pgvector.table` | `MEMORY_PGVECTOR_DSN` |
| ClickHouse inventory reader | `secret.clickhousePassword` | `inventoryConfig.clickhouseHost`, `clickhousePort`, `clickhouseUser`, `clickhouseDatabase` | `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_*` |
| Redis short-term memory | None by default in the lab unless Redis auth is enabled later | `config.memory.redis.endpoint`, `db`, `key_prefix` | `settings.yaml` |
| Qdrant prior-reference lookup | None by default in the lab unless Qdrant auth is enabled later | `config.retrieval.qdrant.endpoint`, `collection`, `top_k`, `min_score` | `settings.yaml` |
| Qdrant future memory adapter | None by default; disabled | `config.memory.qdrant.endpoint`, `collection`, `enabled` | `settings.yaml` |
| Langfuse traces | `secret.langfusePublicKey`, `secret.langfuseSecretKey` | `config.observability.langfuse_endpoint`, `langfuse_enabled` | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` |
| SigNoz/OpenTelemetry traces | None by default | `config.observability.otlp_endpoint`, `signoz_enabled` | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Azure OpenAI LLM | Azure identity/session credentials outside this chart, if used | `config.llm.azure_endpoint`, deployment, API version | Azure identity env/runtime |
| Ollama LLM profiles | None by default | `config.llm.model_profiles.*.base_url` | `settings.yaml` |

## PostgreSQL

PostgreSQL is used for inventory snapshots and pgvector episodic memory.

Inventory DSN:

```yaml
secret:
  postgresDsn: "postgresql://<user>:<password>@postgresql.bosgenesis.svc.cluster.local:5432/<database>"
```

pgvector memory DSN:

```yaml
secret:
  memoryPgvectorDsn: "postgresql://<user>:<password>@postgresql.bosgenesis.svc.cluster.local:5432/<database>"
```

Operational notes:

- URL-encode special characters in the password.
- Keep `inventoryConfig.postgresEnabled: "true"` when PostgreSQL should be the default inventory source.
- Keep `config.memory.pgvector.enabled: true` and `config.memory.episodic_enabled: true` when episodic memory should persist.

Verification:

```powershell
$cfg = Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/config/effective
$cfg.inventory.postgres
$cfg.memory.pgvector
```

The DSNs must appear as `***REDACTED***`.

## ClickHouse

ClickHouse is used as an optional inventory snapshot source.

Credentials and endpoint:

```yaml
inventoryConfig:
  clickhouseEnabled: "true"
  clickhouseHost: "clickhouse.bosgenesis.svc.cluster.local"
  clickhousePort: "8123"
  clickhouseUser: "bosgenesis"
  clickhouseDatabase: "bosgenesis_k8s_ingestion"

secret:
  clickhousePassword: "<clickhouse-password>"
```

Verification:

```powershell
$cfg = Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/config/effective
$cfg.inventory.clickhouse
```

The password must appear as `***REDACTED***`.

## Redis

Redis is the recommended durable backend for short-term run memory.

Default non-secret settings:

```yaml
config:
  memory:
    enabled: true
    short_term_enabled: true
    redis:
      enabled: true
      endpoint: redis-master.bosgenesis.svc.cluster.local:6379
      db: 0
      key_prefix: mop-agent-memory
```

Current lab Redis has no password configured for this agent. If Redis auth is added later, add a dedicated Secret field and environment mapping before storing a password.

Verification after generation:

- API response `memory_status` should be `ok`.
- `artifact.json -> observability.audit_events` should include `memory_read` and `memory_write`.
- `artifact.json -> memory.backend_status.redis` should report `ok` when writes succeed.

## Qdrant

Qdrant has two separate roles:

- prior MoP/installation-note reference lookup during generation;
- future disabled memory adapter.

Read-only reference lookup:

```yaml
config:
  retrieval:
    qdrant:
      enabled: true
      mode: read_only
      endpoint: http://qdrant.bosgenesis.svc.cluster.local:6333
      collection: mop_installation_notes
      top_k: 5
      min_score: 0.72
      ingestion_api_enabled: true
```

Generation must never write to Qdrant automatically. Ingestion is a separate explicit API:

```text
POST /references/qdrant/ingest-mop
```

with `confirm=true`.

If Qdrant auth is introduced later, add an API key Secret field and redact it from effective config and artifacts.

Verification:

- API response `qdrant_lookup_status` should be `references_found`, `no_matches`, `disabled`, or `unavailable`.
- API response `qdrant_reference_count` should reflect accepted citations.
- `artifact.json -> observability.audit_events` should include `qdrant_lookup`.

## Langfuse

Langfuse receives redacted reasoning metadata only. Raw prompts, raw model responses, manifests, Qdrant excerpts, credentials, and production data must not be sent.

Non-secret endpoint:

```yaml
config:
  observability:
    langfuse_enabled: true
    langfuse_endpoint: http://langfuse-web.bosgenesis.svc.cluster.local:3000
```

Secret keys:

```yaml
secret:
  langfusePublicKey: "<langfuse-public-key>"
  langfuseSecretKey: "<langfuse-secret-key>"
```

Verification:

```powershell
$cfg = Invoke-RestMethod http://mop-creation-agent.bosgenesis.local/config/effective
$cfg.observability
```

The public and secret keys must not be printed in plain text. After a generation run:

```powershell
$mopId = "<mop-id>"
$artifact = (Invoke-WebRequest "http://mop-creation-agent.bosgenesis.local/mop-creation/$mopId/artifacts/download?path=artifact.json").Content | ConvertFrom-Json
$artifact.observability.sinks
```

Expected successful status:

```json
{
  "langfuse": "enabled"
}
```

Common statuses:

| Status | Meaning |
|---|---|
| `enabled` | Client initialized and trace emission attempted. |
| `enabled_credentials_missing` | Endpoint is set, but public or secret key is missing. |
| `enabled_sdk_unavailable` | Runtime image does not include the Langfuse package. |
| `enabled_config_failed` | Client initialization failed. |
| `enabled_export_failed` | Client initialized, but trace export failed. |

## SigNoz / OpenTelemetry

SigNoz receives OpenTelemetry phase spans for generation phases. The app uses OTLP/gRPC port `4317`.

Non-secret endpoint:

```yaml
config:
  observability:
    signoz_enabled: true
    otlp_endpoint: http://signoz-otel-collector.signoz.svc.cluster.local:4317
```

No SigNoz credentials are required in the current lab setup.

Verification:

```powershell
$artifact = (Invoke-WebRequest "http://mop-creation-agent.bosgenesis.local/mop-creation/<mop-id>/artifacts/download?path=artifact.json").Content | ConvertFrom-Json
$artifact.observability.sinks
$artifact.observability.trace_ids
```

Expected successful status:

```json
{
  "signoz": "enabled"
}
```

Common statuses:

| Status | Meaning |
|---|---|
| `enabled` | OpenTelemetry tracer provider and OTLP exporter initialized. |
| `enabled_endpoint_missing` | `otlp_endpoint` is not configured. |
| `enabled_sdk_unavailable` | Runtime image does not include OpenTelemetry SDK/exporter packages. |
| `enabled_config_failed` | Exporter initialization failed. |

Search in SigNoz by service name:

```text
bosgenesis-mop-creation-agent
```

Useful trace attributes include:

- `mop.mop_id`
- `mop.run_id`
- `mop.correlation_id`
- `mop.source_namespace`
- `mop.target_namespace`
- `mop.generation_mode`
- `mop.caller`

## MCP Endpoints

MCP endpoints are non-secret service configuration values:

```yaml
config:
  mcp:
    k8s_inspector:
      endpoint: http://bosgenesis-k8s-inspector-mcp.bosgenesis.svc.cluster.local:8080/mcp
      host_header: k8s-inspector.bosgenesis.local
    helm_manager:
      endpoint: http://bosgenesis-helm-manager-mcp.bosgenesis.svc.cluster.local:8080/mcp
      host_header: helm-manager.bosgenesis.local
    data_ingestion_agent:
      endpoint: http://bosgenesis-k8s-data-ingestion-agent.bosgenesis.svc.cluster.local:8080/mcp
      host_header: data-ingestion-agent.bosgenesis.local
```

If an MCP dependency is unavailable, generation should continue with warnings where deterministic fallback is possible.

## LLM Endpoints and Azure Credentials

Ollama model profiles use non-secret in-cluster endpoints:

```yaml
config:
  llm:
    default_model: gemma4:26b
    model_profiles:
      gemma4:26b:
        provider: ollama
        base_url: http://ollama.bosgenesis.svc.cluster.local:11434
      llama70b:
        provider: ollama
        base_url: http://ollama-llama70b.bosgenesis.svc.cluster.local:11434
```

Azure OpenAI profiles should use Azure identity or externally managed credentials. Do not store Azure tokens in chart values.

## Verification Checklist

After any credential change:

1. Redeploy the Helm release.
2. Confirm pod rollout succeeds.
3. Call `/config/effective` and verify secrets are redacted.
4. Trigger a generation run.
5. Poll `GET /mop-creation/{mop_id}` until `generated`.
6. Download `artifact.json`.
7. Confirm:

```text
observability.sinks.signoz == enabled
observability.sinks.langfuse == enabled, if Langfuse keys are configured
memory_status == ok, if memory is enabled
qdrant_lookup_status is not unavailable, if Qdrant is enabled
inventory_source includes postgres or clickhouse when inventory is enabled
```

## Rotation Checklist

When rotating any credential:

1. Update only the ignored credentials values file or external secure values file.
2. Redeploy the Helm release.
3. Confirm the Kubernetes Secret was updated.
4. Restart/rollout the deployment if Helm did not change pod template metadata.
5. Generate a small test MoP.
6. Confirm no plain credential appears in:
   - `/config/effective`;
   - generated `artifact.json`;
   - generated MoP PDF/Markdown;
   - pod logs;
   - Langfuse metadata;
   - SigNoz span attributes.

## Do Not Store

Never store these in tracked files or generated artifacts:

- database passwords;
- PostgreSQL DSNs with passwords;
- ClickHouse passwords;
- Langfuse secret keys;
- API tokens;
- Kubernetes Secret data;
- kubeconfigs;
- Azure access tokens;
- raw LLM prompts containing secret-like values;
- raw model responses containing secret-like values.
