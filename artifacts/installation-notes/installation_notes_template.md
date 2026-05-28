---
artifact_type: installation_notes
schema_version: "1.0"
agent: bosgenesis-mop-creation-agent
mop_id: "{{mop_id}}"
run_id: "{{run_id}}"
correlation_id: "{{correlation_id}}"
generated_at: "{{generated_at}}"
source_namespace: "{{source_namespace}}"
target_namespace: "{{target_namespace}}"
generation_mode: "{{generation_mode}}"
source_snapshot: "{{source_snapshot_id_or_timestamp}}"
status: "{{generation_status}}"
no_secret_values: true
no_production_data: true
qdrant_lookup_status: "{{qdrant_lookup_status}}"
qdrant_reference_count: {{qdrant_reference_count}}
---

# Installation Notes: {{source_namespace}} to {{target_namespace}}

## 1. Purpose

Recreate the Kubernetes/Helm installation footprint from source namespace `{{source_namespace}}` into target namespace `{{target_namespace}}` without copying production data.

These notes are optimized for an autonomous LLM/agent executor. The executor must still require human approval before mutating any cluster or application system.

## 2. Execution Constraints

- Scope is one namespace only.
- Target namespace is `{{target_namespace}}`.
- Use public repositories only.
- Do not copy Kubernetes Secret values.
- Do not copy database rows, MongoDB documents, Kafka messages, Redis values, files, or business payloads.
- Run dry-run commands before real apply/install commands.
- Treat inferred steps as requiring human confirmation.
- Treat Qdrant references as prior guidance only, not current observed facts.

## 3. Required Human Inputs

```yaml
required_human_inputs:
{{required_human_inputs_yaml}}
```

## 4. Evidence Summary

```yaml
evidence:
  source_snapshot: "{{source_snapshot_id_or_timestamp}}"
  kubernetes_mcp:
    status: "{{k8s_mcp_status}}"
    references:
{{k8s_evidence_references_yaml}}
  helm_mcp:
    status: "{{helm_mcp_status}}"
    references:
{{helm_evidence_references_yaml}}
  data_ingestion:
    status: "{{data_ingestion_status}}"
    references:
{{data_ingestion_references_yaml}}
  qdrant_prior_references:
    status: "{{qdrant_lookup_status}}"
    count: {{qdrant_reference_count}}
    references:
{{qdrant_references_yaml}}
```

## 5. Resource Inventory Summary

```yaml
inventory:
  helm_releases:
{{helm_releases_yaml}}
  raw_kubernetes_resources:
{{raw_kubernetes_resources_yaml}}
  application_targets:
{{application_targets_yaml}}
  excluded_resources:
{{excluded_resources_yaml}}
  warnings:
{{warnings_yaml}}
```

## 6. Dependency Graph

```yaml
dependency_order:
  - phase: verify_access
    depends_on: []
  - phase: prepare_target_namespace
    depends_on: [verify_access]
  - phase: prepare_secret_placeholders
    depends_on: [prepare_target_namespace]
  - phase: apply_configmaps
    depends_on: [prepare_secret_placeholders]
  - phase: apply_pvcs
    depends_on: [prepare_target_namespace]
  - phase: install_helm_releases
    depends_on: [apply_configmaps, apply_pvcs, prepare_secret_placeholders]
  - phase: apply_raw_kubernetes_resources
    depends_on: [install_helm_releases, apply_configmaps, apply_pvcs]
  - phase: apply_ingress
    depends_on: [apply_raw_kubernetes_resources]
  - phase: apply_application_metadata
    depends_on: [apply_raw_kubernetes_resources]
    enabled_when: generation_mode == "application"
  - phase: validate
    depends_on: [apply_ingress, apply_application_metadata]
```

## 7. Execution Phases

Each command-bearing step inside a phase must use this shape:

```yaml
step:
  step_id: "<stable-phase-local-id>"
  title: "<short action title>"
  type: "context_check | namespace | secret_placeholder | configmap | pvc | helm | kubernetes | ingress | application_metadata | validation | rollback"
  depends_on: []
  evidence_refs: []
  qdrant_refs: []
  inference:
    label: "observed | inferred | prior_reference | human_input_required"
    confidence: "high | medium | low"
    rationale: "<why this step exists>"
  command: |
    <copyable command or human-action placeholder>
  expected: "<expected state or output>"
  on_failure: "<STOP, investigate, or rollback instruction>"
  mutates_target: true
  requires_human_approval: true
```

### Phase 1 - Verify Access

```yaml
phase_id: verify_access
objective: Confirm source/target context, namespace visibility, and tool availability.
commands:
{{verify_access_commands_yaml}}
expected_outcomes:
{{verify_access_expected_outcomes_yaml}}
stop_conditions:
{{verify_access_stop_conditions_yaml}}
evidence_refs:
{{verify_access_evidence_refs_yaml}}
```

### Phase 2 - Prepare Target Namespace

```yaml
phase_id: prepare_target_namespace
objective: Ensure target namespace exists before applying namespaced resources.
commands:
{{target_namespace_commands_yaml}}
expected_outcomes:
{{target_namespace_expected_outcomes_yaml}}
rollback:
{{target_namespace_rollback_yaml}}
evidence_refs:
{{target_namespace_evidence_refs_yaml}}
```

### Phase 3 - Prepare Secret Placeholders

```yaml
phase_id: prepare_secret_placeholders
objective: Ensure required secret names and keys exist using approved secure values.
manual_inputs:
{{secret_manual_inputs_yaml}}
commands:
{{secret_placeholder_commands_yaml}}
expected_outcomes:
{{secret_expected_outcomes_yaml}}
stop_conditions:
  - Missing approved secret material.
  - Any generated content contains secret values.
evidence_refs:
{{secret_evidence_refs_yaml}}
```

### Phase 4 - Apply ConfigMaps

```yaml
phase_id: apply_configmaps
objective: Apply generated ConfigMap manifests after namespace rewrite and redaction.
commands:
{{configmap_commands_yaml}}
expected_outcomes:
{{configmap_expected_outcomes_yaml}}
rollback:
{{configmap_rollback_yaml}}
evidence_refs:
{{configmap_evidence_refs_yaml}}
```

### Phase 5 - Apply PVCs

```yaml
phase_id: apply_pvcs
objective: Create approved PVCs when storage class and capacity are confirmed.
commands:
{{pvc_commands_yaml}}
expected_outcomes:
{{pvc_expected_outcomes_yaml}}
rollback:
{{pvc_rollback_yaml}}
evidence_refs:
{{pvc_evidence_refs_yaml}}
```

### Phase 6 - Install Helm Releases

```yaml
phase_id: install_helm_releases
objective: Recreate Helm-managed components using generated values files.
step_contract:
  dry_run_required: true
  real_install_requires_successful_dry_run: true
  chart_sources_must_be_public: true
commands:
{{helm_commands_yaml}}
expected_outcomes:
{{helm_expected_outcomes_yaml}}
rollback:
{{helm_rollback_yaml}}
unknowns:
{{helm_unknowns_yaml}}
evidence_refs:
{{helm_evidence_refs_yaml}}
```

### Phase 7 - Apply Raw Kubernetes Resources

```yaml
phase_id: apply_raw_kubernetes_resources
objective: Apply supported non-Helm resources in dependency order.
step_contract:
  dry_run_required: true
  namespace_explicit: true
  blocked_kinds_must_be_excluded: true
commands:
{{raw_kubernetes_commands_yaml}}
expected_outcomes:
{{raw_kubernetes_expected_outcomes_yaml}}
rollback:
{{raw_kubernetes_rollback_yaml}}
evidence_refs:
{{raw_kubernetes_evidence_refs_yaml}}
```

### Phase 8 - Apply Ingress

```yaml
phase_id: apply_ingress
objective: Apply ingress resources after backend services are available.
commands:
{{ingress_commands_yaml}}
expected_outcomes:
{{ingress_expected_outcomes_yaml}}
rollback:
{{ingress_rollback_yaml}}
evidence_refs:
{{ingress_evidence_refs_yaml}}
```

### Phase 9 - Application Metadata Recreation

```yaml
phase_id: apply_application_metadata
enabled_when: generation_mode == "application"
objective: Recreate metadata-only schemas, topics, and topology without data.
targets:
{{application_targets_yaml}}
commands_or_guidance:
{{application_metadata_commands_yaml}}
expected_outcomes:
{{application_metadata_expected_outcomes_yaml}}
rollback:
{{application_metadata_rollback_yaml}}
evidence_refs:
{{application_metadata_evidence_refs_yaml}}
```

### Phase 10 - Validate

```yaml
phase_id: validate
objective: Confirm recreated namespace resources are healthy.
commands:
{{validation_commands_yaml}}
expected_outcomes:
{{validation_expected_outcomes_yaml}}
stop_conditions:
{{validation_stop_conditions_yaml}}
evidence_refs:
{{validation_evidence_refs_yaml}}
```

## 8. Go / No-Go Matrix

```yaml
go_no_go:
{{go_no_go_yaml}}
```

## 9. Rollback Plan

```yaml
rollback:
  trigger_conditions:
{{rollback_trigger_conditions_yaml}}
  helm:
{{helm_rollback_yaml}}
  raw_kubernetes:
{{raw_kubernetes_rollback_yaml}}
  application_metadata:
{{application_metadata_rollback_yaml}}
  namespace_cleanup:
{{namespace_cleanup_rollback_yaml}}
```

## 10. Inference and Confidence

```yaml
inferences:
{{inferences_yaml}}
unknowns:
{{unknowns_yaml}}
confidence_summary:
{{confidence_summary_yaml}}
```

## 11. Excluded Resources

```yaml
excluded_resources:
{{excluded_resources_yaml}}
exclusion_policy:
  - Secret values are never copied.
  - Cluster-scoped resources are out of v1 scope.
  - Unsupported namespaced resources require manual review.
```

## 12. Artifact References

```yaml
artifacts:
  human_mop_pdf: "{{human_mop_pdf_path}}"
  installation_notes: "{{installation_notes_path}}"
  generated_manifests_dir: "{{generated_manifests_dir}}"
  generated_values_dir: "{{generated_values_dir}}"
  evidence_dir: "{{evidence_dir}}"
```

## 13. Final Safety Gate

Before execution, confirm:

- [ ] No secret values appear in this file.
- [ ] No production data appears in this file.
- [ ] All inferred steps are labeled.
- [ ] All required human inputs are available.
- [ ] Dry-run commands are executed before real mutation commands.
- [ ] Human approval is obtained for application-mode schema/topic cleanup.
