# Sample-Derived MoP Template Specification

**Document status:** Initial scaffold  
**Source:** `kubernetes-mop-sample.md`  
**Primary output:** Human-readable MoP content and future production PDF MoP

## 1. Intent

The human-facing MoP must be rendered from the approved sample MoP structure. The current implementation may use Markdown or an internal document model as the primary human content artifact and writes a valid PDF placeholder for API/artifact compatibility. Production-quality PDF rendering is deferred to the PDF renderer phase and must follow this template when implemented.

The LLM/agent-readable installation notes remain Markdown and are optimized for autonomous execution by another agent.

## 2. Required Human MoP Structure

The human MoP content and future production PDF must follow this section order:

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

## 5. BOS Genesis Adaptation

The sample deployment sections must be adapted for namespace mirroring:

- access checks confirm source and target context;
- backup/export captures source manifests and Helm values references;
- deployment execution creates or verifies target namespace, secret placeholders, ConfigMaps, PVCs, Helm releases, raw Kubernetes resources, ingress, and optional application schemas;
- validation checks workloads, services, ingress, Helm release status, PVCs, and application schemas;
- rollback removes target Helm releases and generated raw resources, with namespace deletion only when explicitly approved.

## 6. Future PDF Rendering Requirements

When the production PDF renderer is implemented, the PDF must preserve:

- readable heading hierarchy;
- tables;
- checklists;
- command blocks;
- expected output blocks;
- STOP and rollback callouts;
- Go / No-Go table;
- execution log table;
- footer metadata.

Artifact generation must fail if required sections are missing or if secret-like values or production data appear in the rendered content. Production PDF generation must also fail when these validation rules are violated.
