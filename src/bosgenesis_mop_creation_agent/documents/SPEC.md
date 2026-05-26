# Document Generation Specification

## Intent

`documents/` renders validated evidence and accepted reasoning into output artifacts.

## Required artifact types

- Human-readable MoP PDF.
- LLM/agent-readable Markdown installation notes.
- Generated manifest snippets.
- Generated Helm values snippets.
- Evidence appendix.
- Unknowns and required human inputs list.
- Validation summary.

## Human MoP PDF contract

The human MoP must be rendered to PDF using the approved sample-derived section order:

1. Title
2. Document Header
3. Change Summary
4. Pre-change Checklist
5. Access & Environment Verification
6. Pre-change Backup
7. Stakeholder Notification
8. Deployment Execution
9. Validation
10. Go / No-Go Decision Points
11. Rollback Procedure
12. Post-Change Activities
13. Execution Log
14. Footer

## Markdown installation notes contract

The agent-readable installation notes must include:

- machine-readable metadata;
- execution phases;
- dependency graph or ordered dependency list;
- command blocks;
- expected outcomes;
- validation checks;
- rollback hints;
- evidence references;
- inference labels, confidence, and rationale;
- unknowns and required human inputs;
- explicit no-data-copy and no-secret constraints.

## File contract

Local storage paths:

```text
/data/mops/<file-name>.pdf
/data/mops/<file-name>.installation.md
/data/mops/<mop-id>/generated/*.yaml
/data/mops/<mop-id>/values/*.yaml
/data/mops/<mop-id>/evidence/*.json
```

## Rendering rule

Documents must be deterministic once the evidence bundle and accepted reasoning plan are fixed.
