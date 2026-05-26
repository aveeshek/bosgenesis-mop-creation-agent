# Configuration Specification

## Intent

`config/` defines non-secret configuration contracts for runtime behavior.

## Configuration groups

- Namespace and scope settings.
- Runtime mode settings.
- Generation mode settings.
- MCP dependency URLs and host headers.
- LLM provider and model settings.
- LangChain and LangMem settings.
- Observability settings.
- Artifact output settings.
- Safety and redaction settings.

## Secret handling

Secret values belong only in external secret stores or Kubernetes Secrets. This repository must not contain real credentials.

