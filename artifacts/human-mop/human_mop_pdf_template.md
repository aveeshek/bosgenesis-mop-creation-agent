# MoP: {{mop_title}}

---

## Document Header

| Field | Value |
|---|---|
| **MoP Title** | {{mop_title}} |
| **MoP ID** | {{mop_id}} |
| **Version** | {{mop_version}} |
| **Generator** | bosgenesis-mop-creation-agent |
| **Generated At** | {{generated_at}} |
| **Reviewed By** | {{reviewed_by_placeholder}} |
| **Change Ticket** | {{change_ticket_placeholder}} |
| **Change Window** | {{change_window_placeholder}} |
| **Estimated Duration** | {{estimated_duration}} |
| **Risk Level** | {{risk_level}} |
| **Rollback Time** | {{rollback_time}} |
| **Rollback Approver** | {{rollback_approver_placeholder}} |
| **Source Namespace** | {{source_namespace}} |
| **Target Namespace** | {{target_namespace}} |
| **Generation Mode** | {{generation_mode}} |
| **Source Snapshot** | {{source_snapshot_id_or_timestamp}} |
| **Run ID** | {{run_id}} |
| **Correlation ID** | {{correlation_id}} |

---

## Change Summary

**What:** Recreate the Kubernetes and Helm installation footprint from source namespace `{{source_namespace}}` into target namespace `{{target_namespace}}`.

**Why:** {{change_reason}}

**Impact:** This MoP creates or updates target namespace resources only. It does not copy production data and does not migrate Kubernetes Secret values.

| Category | Count | Notes |
|---|---:|---|
| Helm releases | {{helm_release_count}} | {{helm_release_summary}} |
| Raw Kubernetes resources | {{raw_k8s_resource_count}} | {{raw_k8s_summary}} |
| Application-mode targets | {{application_target_count}} | {{application_summary}} |
| Excluded resources | {{excluded_resource_count}} | {{excluded_summary}} |
| Warnings | {{warning_count}} | {{warning_summary}} |

**Assumptions:**

{{assumptions_list}}

**Unknowns / Required Human Inputs:**

{{unknowns_list}}

---

## Pre-change Checklist

Before starting, confirm all items are checked:

- [ ] Change ticket or approval reference is recorded: `{{change_ticket_placeholder}}`
- [ ] Operator has access to the source cluster context and target cluster context.
- [ ] Target namespace name is confirmed: `{{target_namespace}}`
- [ ] Required secret material is available from approved secure sources.
- [ ] Generated Helm values and manifests have been reviewed for redaction and namespace rewrite.
- [ ] Required public Helm repositories and chart references are reachable.
- [ ] Rollback approver is available: `{{rollback_approver_placeholder}}`
- [ ] Application-mode schema/topology guidance, if present, has been reviewed by the application owner.

---

## 1. Access & Environment Verification

**Step 1.1 - Confirm active Kubernetes context**

```bash
kubectl config current-context
```

**Expected output:**

```text
{{expected_cluster_context}}
```

> STOP if the context is not the intended target cluster.

---

**Step 1.2 - Verify source namespace visibility**

```bash
kubectl get namespace {{source_namespace}}
kubectl get all -n {{source_namespace}}
```

**Expected output:** Namespace exists and source workloads are visible to the operator.

> STOP if the source namespace cannot be inspected. Regenerate this MoP after source evidence is refreshed.

---

**Step 1.3 - Verify or create target namespace**

```bash
kubectl get namespace {{target_namespace}} || kubectl create namespace {{target_namespace}}
kubectl get namespace {{target_namespace}}
```

**Expected output:** Target namespace `{{target_namespace}}` exists.

> STOP if namespace creation is not approved for this change.

---

**Step 1.4 - Verify Helm availability**

```bash
helm version
helm list -n {{target_namespace}}
```

**Expected output:** Helm is installed and can query the target namespace.

---

**Step 1.5 - Verify generated artifact bundle**

```bash
ls -lh {{artifact_bundle_path}}
find {{artifact_bundle_path}} -maxdepth 2 -type f | sort
```

**Expected output:** Generated values, manifests, and evidence references are available.

---

## 2. Pre-change Backup

**Step 2.1 - Export source namespace summary**

```bash
kubectl get all,configmap,pvc,ingress -n {{source_namespace}} -o wide \
  > {{backup_dir}}/{{source_namespace}}-summary-$(date +%F-%H%M).txt
```

**Expected output:** Source namespace summary file is created.

---

**Step 2.2 - Export source manifests without Secret values**

```bash
kubectl get configmap,service,deployment,statefulset,daemonset,job,cronjob,pvc,ingress \
  -n {{source_namespace}} -o yaml \
  > {{backup_dir}}/{{source_namespace}}-non-secret-manifests-$(date +%F-%H%M).yaml
```

**Expected output:** Non-secret source manifest reference is created.

> Do not export Kubernetes Secret data into this backup bundle.

---

**Step 2.3 - Export Helm release references**

```bash
helm list -n {{source_namespace}} > {{backup_dir}}/{{source_namespace}}-helm-releases-$(date +%F-%H%M).txt
{{helm_backup_commands}}
```

**Expected output:** Helm release list and approved values references are captured.

---

## 3. Stakeholder Notification

**Step 3.1 - Notify start of namespace recreation**

Post in the approved deployment channel:

```text
[STARTING] {{mop_id}} - recreating namespace {{source_namespace}} into {{target_namespace}}
Mode: {{generation_mode}}
Change window: {{change_window_placeholder}}
Rollback approver: {{rollback_approver_placeholder}}
Run ID: {{run_id}}
```

---

## 4. Deployment Execution

### 4.1 Target Namespace Preparation

{{target_namespace_preparation_steps}}

---

### 4.2 Secret Placeholders and Required Inputs

The agent does not copy Kubernetes Secret values. Create required secrets manually from approved secure sources before applying workloads that depend on them.

| Secret Name | Required Keys | Source / Owner | Status |
|---|---|---|---|
{{secret_placeholder_rows}}

{{secret_creation_guidance}}

---

### 4.3 ConfigMaps and Static Configuration

{{configmap_execution_steps}}

---

### 4.4 Persistent Volume Claims

{{pvc_execution_steps}}

---

### 4.5 Helm Release Recreation

For each Helm release, run the dry-run command first. Proceed only after dry-run output is reviewed.

{{helm_release_execution_steps}}

---

### 4.6 Raw Kubernetes Resource Recreation

Apply generated manifests in dependency order. Run server-side dry-run before each real apply.

{{raw_kubernetes_execution_steps}}

---

### 4.7 Ingress and External Routing

{{ingress_execution_steps}}

---

### 4.8 Application Schema / Topology Recreation

This section appears only when `application` mode is selected. It must recreate metadata/schema/topology only, never production data.

{{application_mode_execution_steps}}

---

## 5. Validation

**Step 5.1 - Validate Helm releases**

```bash
helm list -n {{target_namespace}}
{{helm_validation_commands}}
```

**Expected output:** Expected Helm releases are deployed and healthy.

---

**Step 5.2 - Validate workloads**

```bash
kubectl get deployment,statefulset,daemonset,job,cronjob -n {{target_namespace}}
kubectl get pods -n {{target_namespace}} -o wide
```

**Expected output:** Workloads are available, and pods are Running or Completed as appropriate.

> STOP and investigate if any pod shows `CrashLoopBackOff`, `Error`, or unexpected restarts.

---

**Step 5.3 - Validate services and endpoints**

```bash
kubectl get service,endpoints -n {{target_namespace}}
```

**Expected output:** Services exist and endpoints are populated where expected.

---

**Step 5.4 - Validate ingress**

```bash
kubectl get ingress -n {{target_namespace}}
{{ingress_validation_commands}}
```

**Expected output:** Ingress resources exist with expected host/path values.

---

**Step 5.5 - Validate application-mode metadata**

{{application_mode_validation_steps}}

---

## 6. Go / No-Go Decision Points

| # | Checkpoint | Expected Result | Outcome | Action if Failed |
|---|---|---|---|---|
| 1 | Target namespace confirmed | `{{target_namespace}}` exists | Pass / Fail | STOP - fix namespace |
| 2 | Secret placeholders resolved | Required secret material created manually | Pass / Fail | STOP - resolve secrets |
| 3 | Helm dry-runs pass | No render/template errors | Pass / Fail | STOP - fix chart/values |
| 4 | Kubectl dry-runs pass | Server accepts manifests | Pass / Fail | STOP - fix manifests |
| 5 | Workloads healthy | Desired replicas ready | Pass / Fail | ROLLBACK or investigate |
| 6 | Services/endpoints healthy | Endpoints populated where expected | Pass / Fail | ROLLBACK or investigate |
| 7 | Ingress valid | Hosts/paths visible | Pass / Fail | Fix ingress or rollback |
| 8 | Application metadata valid | Schemas/topics/topology present, no data copied | Pass / Fail | Manual review |

---

## 7. Rollback Procedure

> Trigger rollback if any Go/No-Go check fails after deployment begins.

**Step 7.1 - Notify rollback is starting**

```text
[ROLLBACK STARTING] {{mop_id}} - target namespace {{target_namespace}}
Reason: <describe failure>
Run ID: {{run_id}}
```

---

**Step 7.2 - Roll back Helm releases**

```bash
{{helm_rollback_commands}}
```

---

**Step 7.3 - Remove raw Kubernetes resources**

```bash
{{raw_kubernetes_rollback_commands}}
```

---

**Step 7.4 - Application-mode cleanup**

{{application_mode_rollback_steps}}

> Application schema/topic cleanup can be destructive. Require human review before running cleanup commands.

---

**Step 7.5 - Optional namespace cleanup**

Only run this if the target namespace was newly created for this change and namespace deletion is approved.

```bash
kubectl delete namespace {{target_namespace}}
```

---

**Step 7.6 - Notify rollback complete**

```text
[ROLLBACK COMPLETE] {{mop_id}} - target namespace {{target_namespace}}
Rollback duration: <X> minutes
Follow-up ticket: <link>
```

---

## 8. Post-Change Activities

- [ ] Update change ticket with final status: Success / Rolled Back / Partial.
- [ ] Attach this MoP PDF and generated installation notes.
- [ ] Attach generated manifest/value/evidence bundle references.
- [ ] Record any command deviations from the MoP.
- [ ] Confirm no production data or secret values were copied.
- [ ] If rolled back, open follow-up defect or post-incident review.
- [ ] If successful, hand off target namespace validation results to the application owner.

---

## Execution Log

| Time (UTC) | Step | Operator | Result | Notes |
|---|---|---|---|---|
|  | Start - context verified |  | Pass / Fail |  |
|  | Pre-checks complete |  | Pass / Fail |  |
|  | Backup captured |  | Pass / Fail |  |
|  | Stakeholders notified |  | Pass / Fail |  |
|  | Secrets prepared |  | Pass / Fail |  |
|  | Helm dry-runs complete |  | Pass / Fail |  |
|  | Kubernetes dry-runs complete |  | Pass / Fail |  |
|  | Deployment complete |  | Pass / Fail |  |
|  | Validation complete |  | Pass / Fail |  |
|  | Change closed |  | Pass / Fail |  |

---

## Evidence and Inference Appendix

### Evidence References

{{evidence_references}}

### Qdrant Prior References

{{qdrant_prior_references}}

### Inferred Guidance

{{inference_labels_and_rationale}}

### Excluded Resources

{{excluded_resources}}

---

*MoP generated by bosgenesis-mop-creation-agent | source={{source_namespace}} | target={{target_namespace}} | run_id={{run_id}} | correlation_id={{correlation_id}}*

