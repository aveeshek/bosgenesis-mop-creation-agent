# Sample-Derived MoP Template Specification

**Document status:** Initial scaffold  
**Source:** `kubernetes-mop-sample.md`  
**Primary output:** Human-readable Markdown MoP content and professional PDF MoP

## 1. Intent

The human-facing Markdown MoP must be rendered from the approved sample MoP structure. The professional PDF uses `artifacts/human-mop/professional_mop_pdf_template.yaml` for a colored executive-review layout while preserving copy-pasteable execution commands, shell syntax, validation steps, and safety controls.

The LLM/agent-readable installation notes remain Markdown and are optimized for autonomous execution by another agent.

## 2. Required Human MoP Structure

The human MoP Markdown content must follow this section order:

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

## 3. Document Header Fields

The header table must include:

- MoP Title
- MoP ID
- Version
- Author or Generator
- Reviewed By
- Change Ticket
- Change Window
- Estimated Duration
- Risk Level
- Rollback Time
- Rollback Approver
- Source Namespace
- Target Namespace
- Generation Mode
- Run ID
- Correlation ID
- Evidence Snapshot ID or Timestamp

Unknown human-governance fields must be represented as placeholders, not omitted.

## 4. Step Format

Operational sections must use numbered steps:

```text
Step <section>.<step> - <action title>
```

Each executable step should include:

- command block;
- expected output or expected state;
- STOP / rollback guidance where applicable;
- evidence reference when useful.

Command blocks must preserve shell syntax exactly, including `&&`, `||`, pipes,
quotes, and namespace arguments.

## 5. BOS Genesis Adaptation

The sample deployment sections must be adapted for namespace mirroring:

- access checks confirm source and target context;
- backup/export captures source manifests and Helm values references;
- deployment execution creates or verifies target namespace, secret placeholders, ConfigMaps, PVCs, Helm releases, raw Kubernetes resources, ingress, and optional application schemas;
- validation checks workloads, services, ingress, Helm release status, PVCs, and application schemas;
- rollback removes target Helm releases and generated raw resources, with namespace deletion only when explicitly approved.

## 6. Professional PDF Rendering Requirements

The professional PDF renderer must preserve:

- title and cover page;
- executive summary;
- namespace analytical summary;
- document quality analysis;
- scope, evidence, and controls;
- platform inventory overview;
- operator execution plan;
- full ordered execution commands from `machine_execution_plan`;
- human-readable validation/evidence matrix with copy-pasteable validation commands;
- STOP and rollback callouts;
- Go / No-Go and rollback controls;
- Appendix A resource snapshot grouped as Helm release, deployment, service, pod, and other resource tables;
- footer metadata and page numbers.

The professional PDF renderer must paginate variable-height tables safely,
redraw table headers after page breaks, and leave enough spacing so tables,
labels, and command blocks never overlap. Raw YAML/JSON dumps and internal MCP
reference lists must not appear in human-facing validation sections.

Artifact generation must fail if required sections are missing or if secret-like values or production data appear in the rendered content. Production PDF generation must also fail when these validation rules are violated.
