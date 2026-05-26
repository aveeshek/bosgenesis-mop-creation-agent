# Rendering Specification

## Intent

`rendering/` converts validated evidence and accepted reasoning plans into Markdown artifacts and generated snippets.

## Future modules

- `mop_template.py`
- `mop_renderer.py`
- `agent_guide_renderer.py`
- `command_builder.py`
- `manifest_normalizer.py`
- `markdown_writer.py`

## Human MoP output

The human MoP renderer must produce the approved 17-section Markdown structure and copyable commands.

## Agent guide output

The agent guide renderer must produce `.agent.md` Markdown with:

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

