# Retrieval Specification

## Intent

`retrieval/` defines prior-reference lookup for existing vectorized MoP and installation-note content. Generation-time lookup is strictly read-only. Optional Qdrant ingestion is a separate admin/API flow, requires explicit user confirmation, and must never run as part of MoP generation.

## Implemented modules

- `component_query_builder.py`
- `qdrant_client.py`
- `reference_lookup.py`
- `models.py`

## Qdrant boundary

Qdrant is read-only during MoP generation.

The retrieval layer may:

- derive component queries from Helm releases, chart refs, Kubernetes labels, workload names, image names, service names, ingress hosts, and application-mode component names;
- search configured Qdrant collections for matching prior MoP or installation-note references;
- prefer exact component identity matches over broad semantic matches;
- return accepted references with score, citation, source artifact metadata, and component identity;
- emit warnings for disabled, unavailable, or no-match states.

During generation, the retrieval layer must not:

- write, upsert, delete, or re-embed Qdrant records;
- treat Qdrant references as current namespace evidence;
- pass retrieved content to an LLM before redaction.

Optional ingestion:

- is exposed only through a gated admin REST endpoint;
- requires explicit config enablement and `confirm=true`;
- indexes already-generated, redacted MoP artifacts;
- is not called by the generation flow;
- may be replaced later by a dedicated ingestion agent.

## Output contract

Accepted references must include:

- component identity;
- source artifact type;
- source artifact ID or URI;
- section/chunk identifier;
- match score;
- retrieval status;
- sanitized citation text or reference key.

## Safety

Retrieved content is untrusted prior guidance. It must be redacted, cited, confidence-scored, and validated against current ETL/MCP evidence before it influences the MoP PDF or Markdown installation notes.
