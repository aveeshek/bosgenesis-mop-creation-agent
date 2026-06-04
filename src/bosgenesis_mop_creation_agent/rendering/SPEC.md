# Rendering Specification

## Intent

`rendering/` converts validated evidence, classification output, and reconstruction plans into sample-format human MoP markdown, a paginated PDF, Markdown installation notes, a standalone machine execution plan YAML file, and generated snippets.

## Current modules

- `artifact_writer.py`: Local artifact writer that renders snapshot-backed, MCP-enriched, and reconstruction-backed human MoP markdown, professional PDF, installation notes markdown, `machine_execution_plan.yaml`, generated manifests, redacted values, and `artifact.json` metadata from the approved artifact templates.
- `pdf_renderer.py`: Native professional PDF renderer driven by `artifacts/human-mop/professional_mop_pdf_template.yaml`.

## Future modules

- `mop_template.py`
- `mop_renderer.py`
- `installation_notes_renderer.py`
- `markdown_writer.py`

## Human MoP output

The current human MoP renderer must produce the approved sample-derived markdown document and a professional, color-styled PDF artifact. The PDF renderer must follow `professional_mop_pdf_template.yaml` and include the cover page, executive summary, namespace analytical summary, document quality analysis, scope/evidence/controls, platform inventory overview, operator execution plan, full ordered execution commands from `machine_execution_plan`, go/no-go and rollback controls, validation/evidence matrix, grouped appendix resource tables, and page footers.

The PDF renderer must not include the removed `Kubernetes Topology View` or
`Platform Dependency Map` sections in the professional PDF template.

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
- bounded LLM reasoning and repair suggestions only as advisory labels, confidence, rationale, and human-review notes.

The same YAML must also be written as `machine_execution_plan.yaml` in the run directory. YAML output must disable aliases/anchors so downstream LLMs can read it without resolving `&id` or `*id` references.

## Command rendering

Rendered commands must:

- include target namespace explicitly;
- include dry-run guidance before real apply/install;
- label inferred chart references or values;
- avoid executable steps for excluded resources.
- preserve shell operators and syntax exactly inside code blocks;
- never replace shell operators such as `&&`, `||`, or `|` with prose-safe text;
- render `Actual Execution Steps - Command Pattern` as ordered command-bearing
  steps from `machine_execution_plan`, not as truncated samples.

## PDF validation rendering

The `Validation and Evidence Matrix` section must:

- show evidence sources in human-readable rows;
- avoid raw YAML/JSON dumps and internal MCP reference lists;
- render validation commands as copy-pasteable steps from the `validate` phase
  of `machine_execution_plan`;
- include expected outcomes when available.

## PDF layout rules

The renderer must:

- paginate variable-height tables safely;
- redraw table headers after page breaks;
- leave stable spacing between tables, labels, and code blocks;
- report a non-zero overflow diagnostic if content cannot be placed without
  clipping or overlap.

## Manifest and values normalization

Rendered snippets are produced by `reconstruction/`. The rendering layer must reference the generated raw manifests and redacted Helm values files, and must not reintroduce blocked resources or secret values into command sections.

## LLM advisory rendering

Bounded reasoning and repair outputs may appear in the Evidence and Inference
Appendix, `artifact.json`, and the installation notes `inferences` block.
These outputs must never alter command blocks, generated manifests, Helm values,
or `machine_execution_plan` executable steps. Every LLM-derived item must be
labeled `llm_suggestion_requires_human_review`, must carry confidence and
rationale, and must have `executable_yaml_allowed: false`.

## Safety

Rendering must fail if required artifact sections are missing or if secret/production data appears in output.
