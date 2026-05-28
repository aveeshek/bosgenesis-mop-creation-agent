# Installation Notes Artifact Specification

## Intent

This folder will hold LLM/agent-readable Markdown installation notes.

The canonical source template for installation notes is:

- `installation_notes_template.md`

## Required traits

- Clear execution phases.
- Structured metadata.
- Idempotent commands.
- Validation checkpoints.
- Machine-friendly dependency ordering.
- Evidence references and inference labels.
- Explicit placeholders for secrets and human-provided inputs.

## Template rules

- Prefer YAML blocks and stable keys where possible.
- Keep phases idempotent and dependency-aware.
- Include rollback metadata for every mutating phase.
- Treat Qdrant references as non-authoritative prior guidance.
- Never include secret values or production data.
