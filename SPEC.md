# Repository Specification

## Intent

This repository defines the spec-driven skeleton for the BOS Genesis MoP Creation Agent.

The agent reads namespace-scoped evidence, reasons over installation provenance, and emits reproducible installation documentation for humans and agents.

## Initial scope

- One namespace only.
- Namespace-only Kubernetes scope.
- Kubernetes and Helm based installation inference.
- Public repositories only.
- No production data export.
- No Kubernetes, Helm, database, stream, or application mutation.

## Core dependencies

- `bosgenesis-k8s-inspector-mcp` for namespace-scoped Kubernetes evidence.
- `bosgenesis-helm-manager-mcp` for Helm release, values, history, manifest, and repository evidence.
- `bosgenesis-k8s-data-ingestion-agent` for normalized historical and analytical runtime evidence.
- LangChain for standalone LLM orchestration.
- LangMem for short-term, episodic, and knowledge memory.
- Langfuse and SigNoz for traceability and observability.

## Non-code constraint

The initial scaffold contains Markdown specifications only. No executable code, dependency manifests, Helm templates, Kubernetes manifests, or scripts are included yet.

