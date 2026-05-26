# Document Generation Specification

## Intent

`documents/` renders validated evidence and accepted reasoning into output artifacts.

## Required artifact types

- Human-readable MoP Markdown.
- LLM/agent-readable installation guide Markdown.
- Generated manifest snippets.
- Generated Helm values snippets.
- Evidence appendix.
- Unknowns and required human inputs list.
- Validation summary.

## Human MoP contract

The human MoP must follow the 17-section output contract:

1. Document Header
2. Change Summary
3. Source and Target Namespace Overview
4. Pre-change Checklist
5. Access and Environment Verification
6. Source Namespace Export/Reference Snapshot
7. Target Namespace Preparation
8. Secret Placeholder and Prerequisite Inputs
9. Helm Release Recreation Steps
10. Raw Kubernetes Resource Recreation Steps
11. Application Schema/Topology Recreation Steps, when selected
12. Validation Steps
13. Go/No-Go Decision Points
14. Rollback Procedure
15. Post-change Activities
16. Execution Log
17. Appendix: Generated Manifests, Helm Values, Evidence, and Unknowns

## Agent guide contract

The agent-readable guide must include:

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
/data/mops/<file-name>.md
/data/mops/<file-name>.agent.md
/data/mops/<mop-id>/generated/*.yaml
/data/mops/<mop-id>/values/*.yaml
/data/mops/<mop-id>/evidence/*.json
```

## Rendering rule

Documents must be deterministic once the evidence bundle and accepted reasoning plan are fixed.

