from pathlib import Path

from bosgenesis_mop_creation_agent.rendering.pdf_renderer import render_human_mop_pdf


def test_phase7_pdf_renderer_creates_paginated_readable_pdf(tmp_path: Path) -> None:
    markdown = "# MoP: Phase 7 Renderer Test\n\n## Execution Log\n\n## Evidence and Inference Appendix\n"
    output_path = tmp_path / "mop.pdf"
    context = {
        "mop_title": "Namespace Recreation MoP - bosgenesis to bosgenesis-copy",
        "mop_id": "mop-1",
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "generated_at": "2026-06-04T00:00:00Z",
        "source_namespace": "bosgenesis",
        "target_namespace": "bosgenesis-copy",
        "generation_mode": "platform-only",
        "helm_release_count": "12",
        "raw_k8s_resource_count": "42",
        "application_target_count": "0",
        "excluded_resource_count": "1",
        "warning_count": "2",
        "warning_summary": "manual_review_required:Pod:runtime_artifacts_skipped",
        "change_reason": "Generate a review-ready professional MoP.",
        "helm_release_summary": "Stored snapshot includes Helm releases.",
        "raw_k8s_summary": "Deployments, services, configmaps, and ingress.",
        "application_summary": "Application mode not selected.",
        "excluded_summary": "Secrets excluded.",
        "source_snapshot_id_or_timestamp": "snapshot-1",
        "qdrant_reference_count": "3",
        "qdrant_lookup_status": "references_found",
        "evidence_references": "postgres snapshot; k8s inspector mcp; helm manager mcp",
        "inference_labels_and_rationale": "LLM suggestions require human review.",
        "required_human_inputs_yaml": "  - approved secret material",
        "machine_execution_plan_yaml": """
machine_execution_plan:
  schema_version: '1.0'
  phases:
    - phase_id: verify_access
      depends_on: []
      objective: Verify local artifact bundle.
      steps:
        - step_id: verify-artifact-bundle
          phase_id: verify_access
          title: Verify generated artifact bundle
          type: context_check
          commands:
            - kind: check
              command: test -f artifact.json && test -d generated && test -d values
          expected_outcomes:
            - artifact.json, generated/, and values/ are present.
          mutates_target: false
          requires_human_approval: false
    - phase_id: prepare_target_namespace
      depends_on: []
      objective: Ensure namespace exists.
      steps:
        - step_id: prepare-target-namespace
          phase_id: prepare_target_namespace
          title: Ensure namespace bosgenesis-copy exists
          type: namespace
          commands:
            - kind: check
              command: kubectl get namespace bosgenesis-copy
            - kind: apply
              command: kubectl get namespace bosgenesis-copy || kubectl create namespace bosgenesis-copy
          expected_outcomes:
            - Namespace bosgenesis-copy exists.
          mutates_target: true
          requires_human_approval: true
    - phase_id: install_helm_releases
      depends_on: [prepare_target_namespace]
      objective: Install Helm releases.
      steps:
        - step_id: install-api
          phase_id: install_helm_releases
          title: Install Helm release api
          type: helm
          commands:
            - kind: dry_run
              command: helm upgrade --install api example/api --namespace bosgenesis-copy -f values/api-values.yaml --dry-run
            - kind: apply
              command: helm upgrade --install api example/api --namespace bosgenesis-copy -f values/api-values.yaml
          expected_outcomes:
            - Helm release api is deployed.
          mutates_target: true
          requires_human_approval: true
    - phase_id: validate
      depends_on: [install_helm_releases]
      objective: Validate namespace.
      steps:
        - step_id: validate-all
          phase_id: validate
          title: Validate recreated resources
          type: validation
          commands:
            - kind: check
              command: kubectl get all -n bosgenesis-copy
          expected_outcomes:
            - Workloads and services are visible.
          mutates_target: false
          requires_human_approval: false
""",
        "professional_resource_snapshot": {
            "helm_releases": [
                {
                    "release_name": "api",
                    "namespace": "bosgenesis",
                    "chart_name": "example/api",
                    "chart_version": "1.2.3",
                    "status": "deployed",
                }
            ],
            "resources_by_kind": {
                "Deployment": [
                    {
                        "name": "api-deployment",
                        "namespace": "bosgenesis",
                        "status": "available",
                        "category": "helm_managed",
                    }
                ],
                "Service": [
                    {
                        "name": "api-service",
                        "namespace": "bosgenesis",
                        "status": "ClusterIP",
                        "category": "helm_managed",
                    }
                ],
                "Pod": [
                    {
                        "name": "api-pod-abc",
                        "namespace": "bosgenesis",
                        "status": "Running",
                        "category": "warning_only",
                    }
                ],
            },
            "excluded_resources": [
                {
                    "kind": "Secret",
                    "name": "api-secret",
                    "namespace": "bosgenesis",
                    "reason": "secret values are excluded",
                }
            ],
        },
        "target_namespace_commands_yaml": "kubectl get namespace bosgenesis-copy || kubectl create namespace bosgenesis-copy",
        "helm_commands_yaml": "helm upgrade --install api example/api -n bosgenesis-copy --dry-run",
        "raw_kubernetes_commands_yaml": "kubectl apply -f generated/deployment-api.yaml -n bosgenesis-copy --dry-run=server",
        "validation_commands_yaml": "kubectl get all -n bosgenesis-copy",
        "rollback_trigger_conditions_yaml": "  - Any approved install/apply command fails after mutation begins.",
        "k8s_mcp_status": "used",
        "k8s_evidence_references_yaml": "  - k8s_inspector_mcp",
        "helm_mcp_status": "used",
        "helm_evidence_references_yaml": "  - helm_manager_mcp",
        "data_ingestion_status": "used",
        "data_ingestion_references_yaml": "  - data_ingestion_mcp",
        "helm_releases_yaml": "  - release_name: api\n    namespace: bosgenesis",
        "raw_kubernetes_resources_yaml": "  - kind: Deployment\n    name: api\n    namespace: bosgenesis",
        "excluded_resources_yaml": "  - kind: Secret\n    name: api-secret",
    }

    result = render_human_mop_pdf(markdown, output_path, context=context)
    pdf_bytes = output_path.read_bytes()

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Type /Page" in pdf_bytes
    assert b"Page 1 of" in pdf_bytes
    assert b"Executive Summary" in pdf_bytes
    assert b"Kubernetes Topology View" not in pdf_bytes
    assert b"Platform Dependency Map" not in pdf_bytes
    assert b"test -f artifact.json && test -d generated && test -d values" in pdf_bytes
    assert b"andand" not in pdf_bytes
    assert b"kubectl get namespace" in pdf_bytes
    assert b"helm upgrade --install api example/api" in pdf_bytes
    assert b"kubectl get all -n bosgenesis-copy" in pdf_bytes
    assert b"Copy-Paste Validation Steps" in pdf_bytes
    assert b"k8s_inspector_mcp" not in pdf_bytes
    assert b"api-deployment" in pdf_bytes
    assert b"api-service" in pdf_bytes
    assert b"api-pod-abc" in pdf_bytes
    assert result.metadata.renderer == "phase7_professional_pdf_renderer"
    assert result.metadata.template_id == "bosgenesis_professional_mop_pdf"
    assert result.metadata.template_version == "1.1"
    assert result.metadata.page_count >= 11
    assert result.metadata.overflow_count == 0
    assert result.metadata.section_order == [
        "Title and Cover Page",
        "Executive Summary",
        "Namespace Analytical Summary",
        "Document Quality Analysis",
        "Scope, Source Evidence, and Controls",
        "Recreated Platform Inventory",
        "Execution Plan - Operator View",
        "Actual Execution Steps - Command Pattern",
        "Go / No-Go and Rollback Controls",
        "Validation and Evidence Matrix",
        "Appendix A - Resource List Snapshot",
    ]
