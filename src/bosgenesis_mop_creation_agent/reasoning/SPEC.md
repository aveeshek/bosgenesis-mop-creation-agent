# Reasoning Specification

## Intent

`reasoning/` hosts deterministic and non-deterministic installation inference workflows.

## Responsibilities

- Determine likely installation mechanisms.
- Reconstruct dependency graph and ordering.
- Classify Helm-managed versus raw Kubernetes resources.
- Infer Helm chart and values requirements.
- Infer raw Kubernetes manifest requirements.
- Identify gaps and required human inputs.
- Use accepted Qdrant prior references as non-authoritative guidance when available.
- Assign confidence levels to inferred steps.
- Produce a reasoning plan for both the human MoP PDF and Markdown installation notes.

## Deterministic-first rule

The reasoning layer must first use deterministic evidence:

- Helm metadata;
- Helm release manifests;
- labels and annotations;
- owner references;
- resource kind safety policy;
- snapshot provenance;
- MCP evidence freshness.

LLM reasoning is used only for ambiguity, gaps, ordering, public repository hints, values reconstruction guidance, and application-mode metadata guidance.

Qdrant prior references may inform ambiguity resolution, but current ETL/MCP evidence remains authoritative.

## LLM rule

LLM reasoning must:

- receive redacted evidence only;
- respect single-namespace, namespace-only, Kubernetes/Helm, public-repository-only v1 scope;
- never invent secret values;
- never produce production data;
- label observed facts, inferred facts, confidence, rationale, and unknowns;
- label Qdrant-derived content as prior reference guidance;
- be validated before artifact delivery.

## Memory usage

Reasoning may retrieve and store non-secret summaries through LangMem-backed short-term, episodic, and knowledge memory.
