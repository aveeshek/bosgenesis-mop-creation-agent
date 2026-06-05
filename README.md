# BOS Genesis MoP Creation Agent

`bosgenesis-mop-creation-agent` is a spec-first, LLM-assisted agent for reconstructing how a single BOS Genesis Kubernetes namespace was installed and generating reproducible installation documentation.

The initial target is namespace-only, public-repository, Kubernetes-and-Helm based environments. The default namespace is `bosgenesis`.

## Primary outputs

- Human-readable Method of Procedure PDF rendered from the approved sample MoP format for manual execution.
- LLM/agent-readable Markdown installation notes for autonomous execution by another agent.

## Modes

- `platform-only`: infer and document Kubernetes resources, Helm releases, charts, values shape, manifests, services, ingress, PVCs, configmaps, jobs, cronjobs, and non-secret dependency ordering.
- `application`: defined as a future/backlog mode for metadata-only schema and topology inference. Phase 12 is intentionally skipped for now; current delivery focus remains `platform-only`.

## Runtime forms

- On-demand MCP server integrated with Codex, where Codex can call the agent repeatedly to refine MoP artifacts.
- Standalone REST-triggered agent that uses configured LLM profiles through LangGraph/LangChain and optional Phase 11 memory.

## Phase 0 runtime

The current implementation includes the Phase 0 foundation and Phase 1 API/MCP contract:

- FastAPI application shell.
- `GET /health`.
- `GET /config/effective` with redaction.
- `POST /mop-creation/generate` returning stub run and artifact metadata.
- `GET /mop-creation/{mop_id}`.
- `GET /mop-creation/latest`.
- MCP-style contract tools for health, generate, get, latest, and effective config.
- YAML/environment config loading.
- JSON structured logging.
- Dockerfile, Helm chart skeleton, `playbook/deploy.sh`, and `playbook/uninstaller.sh`.
- Optional Helm-managed Ingress for exposing the health/config API through the cluster ingress controller.
- Basic pytest and Ruff CI.

Run locally:

```bash
python -m pip install -e ".[dev]"
bosgenesis-mop-creation-agent
```

Deploy with Helm:

```bash
IMAGE_REPOSITORY=<registry>/bosgenesis-mop-creation-agent IMAGE_TAG=<tag> ./playbook/deploy.sh
```

Credential and service endpoint updates are documented in
[docs/CREDENTIALS.md](docs/CREDENTIALS.md). Real credentials belong only in the
ignored `charts/bosgenesis-mop-creation-agent/values.credentials.yaml` file or a
secure values file passed through `HELM_VALUES_FILE`; never commit credentials.

With a custom ingress host:

```bash
INGRESS_HOST=mop-creation-agent.bosgenesis.local IMAGE_REPOSITORY=<registry>/bosgenesis-mop-creation-agent IMAGE_TAG=<tag> ./playbook/deploy.sh
```

Phase 1 REST contract test:

```bash
curl -X POST http://localhost:8080/mop-creation/generate \
  -H "Content-Type: application/json" \
  -d '{"target_namespace":"bosgenesis-copy-dev","caller":"curl","correlation_id":"demo-correlation"}'

curl http://localhost:8080/mop-creation/latest
```

Phase 1 MCP-style contract test:

```bash
curl http://localhost:8080/mcp/tools

curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"mop_creation_health","arguments":{}}}'
```

Phase 1 generation returns IDs, trace placeholders, and artifact paths only. It does not call Kubernetes, Helm, Qdrant, or datastore integrations yet.

## Safety posture

The agent is read-only during discovery and document generation. It must never populate data, expose secrets, or mutate runtime infrastructure.
