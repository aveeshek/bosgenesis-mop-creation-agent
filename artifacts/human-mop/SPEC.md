# Human MoP Artifact Specification

## Intent

This folder will hold generated human-readable Method of Procedure PDF documents.

The canonical source template for rendering the human-facing PDF MoP is:

- `human_mop_pdf_template.md`

## Required sections

- Title.
- Document Header.
- Change Summary.
- Pre-change Checklist.
- Access & Environment Verification.
- Pre-change Backup.
- Stakeholder Notification.
- Deployment Execution.
- Validation.
- Go / No-Go Decision Points.
- Rollback Procedure.
- Post-Change Activities.
- Execution Log.
- Footer.

## Template rules

- Keep operational steps copyable and namespace-explicit.
- Preserve STOP, rollback, and expected-output guidance.
- Keep all secret values as placeholders.
- Label Qdrant content as prior reference guidance.
- Label inferred content with confidence and rationale.
