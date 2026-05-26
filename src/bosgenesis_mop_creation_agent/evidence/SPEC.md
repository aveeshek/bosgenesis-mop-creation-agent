# Evidence Specification

## Intent

`evidence/` defines normalized evidence bundles, provenance, citations, and evidence-to-artifact traceability.

## Responsibilities

- Normalize raw MCP responses.
- Normalize snapshot records.
- Merge snapshot, Kubernetes, Helm, and data-ingestion evidence.
- Index resources by kind, name, namespace, labels, annotations, owner references, and Helm release association.
- Preserve evidence provenance.
- Produce citation IDs for both output artifacts.
- Mark redacted, missing, unavailable, and inferred evidence explicitly.

## Evidence categories

- PostgreSQL ETL snapshot evidence.
- ClickHouse analytical inventory evidence.
- Kubernetes Inspector MCP evidence.
- Helm Manager MCP evidence.
- Data Ingestion Agent evidence.
- Application-mode metadata evidence.
- Explicit LLM inference with confidence and rationale.

## Citation contract

Every generated step in the human MoP and agent guide must be backed by a citation or labeled inference.

## Safety

Evidence bundles passed to LLM, memory, persistence, or rendering must be redacted.

