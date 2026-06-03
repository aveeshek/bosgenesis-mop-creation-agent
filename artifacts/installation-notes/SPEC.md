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
- A canonical `machine_execution_plan` YAML block that downstream agents parse first.
- Evidence references and inference labels.
- Explicit placeholders for secrets and human-provided inputs.

## Template rules

- Prefer YAML blocks and stable keys where possible.
- Keep the `machine_execution_plan` block deterministic and free of prose-only instructions.
- Each machine step must include `step_id`, `phase_id`, `type`, `commands`, `expected_outcomes`, `evidence_refs`, `inference`, `required_human_inputs`, `rollback_commands`, `mutates_target`, and `requires_human_approval`.
- Keep phases idempotent and dependency-aware.
- Include rollback metadata for every mutating phase.
- Treat Qdrant references as non-authoritative prior guidance.
- Never include secret values or production data.
