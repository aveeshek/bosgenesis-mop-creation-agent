# Human MoP Artifact Specification

## Intent

This folder will hold generated human-readable Method of Procedure PDF documents.

The canonical source templates for rendering the human-facing MoP are:

- `human_mop_pdf_template.md`
- `professional_mop_pdf_template.yaml`

## Required sections

- Title and Cover Page.
- Executive Summary.
- Namespace Analytical Summary.
- Document Quality Analysis.
- Scope, Source Evidence, and Controls.
- Recreated Platform Inventory.
- Execution Plan - Operator View.
- Actual Execution Steps - Command Pattern.
- Go / No-Go and Rollback Controls.
- Validation and Evidence Matrix.
- Appendix A - Resource List Snapshot.

## Template rules

- Keep operational steps copyable and namespace-explicit.
- Preserve shell operators and command syntax exactly inside command blocks.
- Preserve STOP, rollback, and expected-output guidance.
- Keep all secret values as placeholders.
- Label Qdrant content as prior reference guidance.
- Label inferred content with confidence and rationale.

## PDF rendering rules

- Render the PDF from `professional_mop_pdf_template.yaml` and the resolved generation context.
- Preserve the professional section order in the template.
- Keep full execution commands, go/no-go checkpoints, rollback controls, stakeholder placeholders, grouped resource tables, and evidence matrix content readable.
- Render `Actual Execution Steps - Command Pattern` as ordered command steps from `machine_execution_plan`, not as example command fragments.
- Render `Validation and Evidence Matrix` as human-readable evidence rows plus copy-pasteable validation steps; do not dump raw YAML or JSON into this human section.
- Render `Appendix A - Resource List Snapshot` as grouped tables for Helm releases and Kubernetes resource kinds such as Deployments, Services, Pods, ConfigMaps, PVCs, Ingresses, Jobs, and warning/excluded resources.
- Wrap long text and command lines instead of clipping them.
- Ensure tables, paragraphs, and code blocks have stable spacing and never overlap.
- Use a colored professional visual theme rather than a black-and-white text dump.
- Record renderer metadata such as template id/version, page count, section order, and overflow count in `artifact.json`.
