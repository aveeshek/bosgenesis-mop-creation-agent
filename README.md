# BOS Genesis MoP Creation Agent

`bosgenesis-mop-creation-agent` is a spec-first, LLM-assisted agent for reconstructing how a single BOS Genesis Kubernetes namespace was installed and generating reproducible installation documentation.

The initial target is namespace-only, public-repository, Kubernetes-and-Helm based environments. The default namespace is `bosgenesis`.

## Primary outputs

- Human-readable Method of Procedure PDF rendered from the approved sample MoP format for manual execution.
- LLM/agent-readable Markdown installation notes for autonomous execution by another agent.

## Modes

- `platform-only`: infer and document Kubernetes resources, Helm releases, charts, values shape, manifests, services, ingress, PVCs, configmaps, jobs, cronjobs, and non-secret dependency ordering.
- `application`: platform-only plus best-effort schema and topology inference for databases, caches, streams, and application components through approved MCP/data-ingestion boundaries and provided credentials.

## Runtime forms

- On-demand MCP server integrated with Codex, where Codex can call the agent repeatedly to refine MoP artifacts.
- Standalone REST-triggered agent that uses an external LLM, initially GPT-4.1 mini, through LangGraph/LangChain and LangMem-backed memory.

## Phase 0 runtime

The current implementation is the foundation skeleton:

- FastAPI application shell.
- `GET /health`.
- `GET /config/effective` with redaction.
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

With a custom ingress host:

```bash
INGRESS_HOST=mop-creation-agent.bosgenesis.local IMAGE_REPOSITORY=<registry>/bosgenesis-mop-creation-agent IMAGE_TAG=<tag> ./playbook/deploy.sh
```

## Safety posture

The agent is read-only during discovery and document generation. It must never populate data, expose secrets, or mutate runtime infrastructure.
