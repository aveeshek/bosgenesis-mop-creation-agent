# Rendering Specification

## Intent

`rendering/` converts validated evidence, classification output, and reconstruction plans into sample-format human MoP markdown, a PDF placeholder, Markdown installation notes, a standalone machine execution plan YAML file, and generated snippets.

## Current modules

- `artifact_writer.py`: Local artifact writer that renders snapshot-backed, MCP-enriched, and reconstruction-backed human MoP markdown, PDF placeholder, installation notes markdown, `machine_execution_plan.yaml`, generated manifests, redacted values, and `artifact.json` metadata from the approved artifact templates.

## Future modules

- `mop_template.py`
- `mop_renderer.py`
- `pdf_renderer.py`
- `installation_notes_renderer.py`
- `markdown_writer.py`

## Human MoP output

The current human MoP renderer must produce the approved sample-derived markdown document and a valid PDF placeholder artifact. Production-quality PDF rendering is intentionally deferred while Phase 8 focuses on agent-readable installation notes.

## Installation notes output

The installation notes renderer must produce `.installation.md` Markdown with:

- machine-readable metadata;
- canonical `machine_execution_plan` YAML that another agent can parse without relying on prose;
- execution phases;
- dependency graph;
- commands;
- validation checks;
- rollback hints;
- evidence references;
- inference labels;
- unknowns and human inputs.

The `machine_execution_plan` block is the primary agent-readable contract. It must include:

- an executor contract with dry-run, approval, no-secret, and target-namespace-only rules;
- ordered phase dependencies;
- command steps grouped by phase;
- command kinds such as `check`, `dry_run`, `apply`, and `validate`;
- expected outcomes for every command-bearing step;
- evidence references and inference labels for every step;
- required human inputs for missing chart references, secret material, and application metadata gaps.

The same YAML must also be written as `machine_execution_plan.yaml` in the run directory. YAML output must disable aliases/anchors so downstream LLMs can read it without resolving `&id` or `*id` references.

## Command rendering

Rendered commands must:

- include target namespace explicitly;
- include dry-run guidance before real apply/install;
- label inferred chart references or values;
- avoid executable steps for excluded resources.

## Manifest and values normalization

Rendered snippets are produced by `reconstruction/`. The rendering layer must reference the generated raw manifests and redacted Helm values files, and must not reintroduce blocked resources or secret values into command sections.

## Safety

Rendering must fail if required artifact sections are missing or if secret/production data appears in output.
