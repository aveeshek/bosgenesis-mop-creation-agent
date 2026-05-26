# Evidence Specification

## Intent

`evidence/` defines normalized evidence bundles, provenance, citations, and evidence-to-artifact traceability.

## Responsibilities

- Normalize raw MCP responses.
- Normalize snapshot records.
- Merge snapshot, Kubernetes, Helm, and data-ingestion evidence.
- Index resources by kind, name, namespace, labels, annotations, owner references, and Helm release association.
- Attach read-only Qdrant prior references as cited guidance when component matches are found.
- Preserve evidence provenance.
- Produce citation IDs for both the MoP PDF and Markdown installation notes.
- Mark redacted, missing, unavailable, and inferred evidence explicitly.

## Evidence categories

- PostgreSQL ETL snapshot evidence.
- ClickHouse analytical inventory evidence.
- Kubernetes Inspector MCP evidence.
- Helm Manager MCP evidence.
- Data Ingestion Agent evidence.
- Qdrant prior MoP/installation-note references for matching components.
- Application-mode metadata evidence.
- Explicit LLM inference with confidence and rationale.

## Citation contract

Every generated step in the human MoP PDF and Markdown installation notes must be backed by a citation or labeled inference.

Qdrant citations must be labeled as prior references and must not be presented as current observed namespace evidence.

## Safety

Evidence bundles passed to LLM, memory, persistence, or rendering must be redacted.
