# Repository Specification

## Intent

This repository defines and implements the spec-driven BOS Genesis MoP Creation Agent.

The agent reads namespace-scoped evidence, reasons over installation provenance, and emits a human MoP PDF plus Markdown installation notes for agents.

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
- LangGraph for standalone workflow/state orchestration, with LangChain for model, prompt, and tool abstractions where useful.
- LangMem-shaped in-process memory, Redis durable short-term memory, and PostgreSQL/pgvector durable episodic memory; Qdrant and Letta memory adapters remain disabled future scope.
- Langfuse and SigNoz for traceability and observability.
- Phase 15 release-candidate validation through deployment docs, sample API
  requests, operational runbook, versioned Helm values, and end-to-end platform
  generation checks.

## Implementation constraint

The implementation must remain spec-driven. Behavioral changes should update the relevant `SPEC.md` and `docs/` contracts before or alongside code, chart, script, or artifact-template changes.

## Sample artifacts

`samples/` contains non-secret request examples for Postman, curl, PowerShell,
and release-candidate validation. Samples must never contain real credentials or
production target namespaces.
