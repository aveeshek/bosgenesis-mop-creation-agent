# BOS Genesis MoP Creation Agent

`bosgenesis-mop-creation-agent` is a spec-first, LLM-assisted agent for reconstructing how a single BOS Genesis Kubernetes namespace was installed and generating reproducible installation documentation.

The initial target is namespace-only, public-repository, Kubernetes-and-Helm based environments. The default namespace is `bosgenesis`.

## Primary outputs

- Human-readable Method of Procedure document for manual execution.
- LLM/agent-readable Markdown installation guide for autonomous execution by another agent.

## Modes

- `platform-only`: infer and document Kubernetes resources, Helm releases, charts, values shape, manifests, services, ingress, PVCs, configmaps, jobs, cronjobs, and non-secret dependency ordering.
- `application`: platform-only plus best-effort schema and topology inference for databases, caches, streams, and application components through approved MCP/data-ingestion boundaries and provided credentials.

## Runtime forms

- On-demand MCP server integrated with Codex, where Codex can call the agent repeatedly to refine MoP artifacts.
- Standalone REST-triggered agent that uses an external LLM, initially GPT-4.1 mini, through LangChain and LangMem-backed memory.

## Safety posture

The agent is read-only during discovery and document generation. It must never populate data, expose secrets, or mutate runtime infrastructure.

