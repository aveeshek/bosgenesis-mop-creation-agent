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

The human MoP must be rendered to PDF using the approved professional section order:

1. Title and Cover Page
2. Executive Summary
3. Namespace Analytical Summary
4. Document Quality Analysis
5. Scope, Source Evidence, and Controls
6. Recreated Platform Inventory
7. Execution Plan - Operator View
8. Actual Execution Steps - Command Pattern
9. Go / No-Go and Rollback Controls
10. Validation and Evidence Matrix
11. Appendix A - Resource List Snapshot

The PDF renderer must use the professional YAML visual template, paginate the
document, wrap long prose and command lines, render table rows and code blocks
in readable form, include page numbers, use color for visual hierarchy, and
record template id/version, page count, section order, and overflow diagnostics
in artifact metadata.

`Actual Execution Steps - Command Pattern` must be a complete operator runbook
derived from the generated `machine_execution_plan`, with commands shown one by
one in execution order. It must preserve shell syntax exactly, including
operators such as `&&`, `||`, pipes, quotes, and namespace arguments.

`Validation and Evidence Matrix` must be human-readable. It may summarize
evidence sources in tables, but validation actions must be rendered as
copy-pasteable commands and expected outcomes, not raw YAML or JSON blocks.

`Appendix A - Resource List Snapshot` must use grouped tables for Helm releases
and Kubernetes resources, including Deployments, StatefulSets, DaemonSets,
Services, Ingresses, ConfigMaps, PVCs, Jobs, CronJobs, Pods, warning-only items,
and excluded resources when present.

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
