# Retrieval Specification

## Intent

`retrieval/` defines read-only prior-reference lookup for existing vectorized MoP and installation-note content.

## Future modules

- `component_query_builder.py`
- `qdrant_reference_finder.py`
- `reference_models.py`

## Qdrant boundary

Qdrant is read-only for this agent.

The retrieval layer may:

- derive component queries from Helm releases, chart refs, Kubernetes labels, workload names, image names, service names, ingress hosts, and application-mode component names;
- search configured Qdrant collections for matching vectorized MoP or installation-note references;
- return accepted references with score, citation, source artifact metadata, and component identity;
- emit warnings for disabled, unavailable, or no-match states.

The retrieval layer must not:

- write, upsert, delete, or re-embed Qdrant records;
- own ingestion or vectorization;
- treat Qdrant references as current namespace evidence;
- pass retrieved content to an LLM before redaction.

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
