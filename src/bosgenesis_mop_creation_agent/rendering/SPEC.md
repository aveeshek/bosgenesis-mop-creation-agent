# Rendering Specification

## Intent

`rendering/` converts validated evidence and accepted reasoning plans into a sample-format MoP document model, PDF artifact, Markdown installation notes, and generated snippets.

## Current modules

- `artifact_writer.py`: Phase 3 local artifact writer that renders snapshot-backed human MoP markdown, PDF placeholder, installation notes markdown, and `artifact.json` metadata from the approved artifact templates.

## Future modules

- `mop_template.py`
- `mop_renderer.py`
- `pdf_renderer.py`
- `installation_notes_renderer.py`
- `command_builder.py`
- `manifest_normalizer.py`
- `markdown_writer.py`

## Human MoP PDF output

The human MoP renderer must produce the approved sample-derived document model and PDF output with copyable commands, expected output blocks, STOP/rollback callouts, Go / No-Go table, execution log, and footer.

## Installation notes output

The installation notes renderer must produce `.installation.md` Markdown with:

- machine-readable metadata;
- execution phases;
- dependency graph;
- commands;
- validation checks;
- rollback hints;
- evidence references;
- inference labels;
- unknowns and human inputs.

## Command rendering

Rendered commands must:

- include target namespace explicitly;
- include dry-run guidance before real apply/install;
- label inferred chart references or values;
- avoid executable steps for excluded resources.

## Manifest and values normalization

Rendered snippets must remove runtime metadata, rewrite namespace to target namespace, and redact secret-like values.

## Safety

Rendering must fail if required artifact sections are missing or if secret/production data appears in output.
