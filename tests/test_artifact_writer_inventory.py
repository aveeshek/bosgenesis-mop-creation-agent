from datetime import UTC, datetime
import json
from pathlib import Path

import yaml

from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest
from bosgenesis_mop_creation_agent.rendering.artifact_writer import LocalArtifactWriter
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)


def test_artifact_writer_includes_snapshot_inventory_counts(tmp_path) -> None:
    inventory = NormalizedInventory(
        source="postgres",
        namespace="bosgenesis",
        snapshot_id="run-123",
        run_id="run-123",
        resources=[
            InventoryResource(kind="Deployment", name="api", namespace="bosgenesis", source="k8s"),
            InventoryResource(kind="Service", name="api", namespace="bosgenesis", source="k8s"),
        ],
        helm_releases=[
            InventoryHelmRelease(
                release_name="api",
                namespace="bosgenesis",
                chart_name="example/api",
                status="deployed",
            )
        ],
    )

    result = LocalArtifactWriter(str(tmp_path)).write(
        mop_id="mop-123",
        run_id="run-abc",
        correlation_id="corr-abc",
        source_namespace="bosgenesis",
        request=MoPGenerationRequest(target_namespace="bosgenesis-copy-dev"),
        created_at=datetime(2026, 5, 27, tzinfo=UTC),
        warnings=["phase4_mcp_enrichment_not_configured"],
        inventory=inventory,
        snapshot_sources_attempted=["postgres"],
        mcp_sources_attempted=["k8s_inspector_mcp", "helm_manager_mcp"],
    )

    manifest = json.loads(Path(result.artifact_manifest_path).read_text(encoding="utf-8"))
    human_mop = Path(result.human_mop_markdown_path).read_text(encoding="utf-8")
    installation_notes = Path(result.installation_notes_path).read_text(encoding="utf-8")

    assert manifest["inventory"]["source"] == "postgres"
    assert manifest["inventory"]["snapshot_id"] == "run-123"
    assert manifest["inventory"]["resource_count"] == 2
    assert manifest["inventory"]["helm_release_count"] == 1
    assert manifest["human_mop_pdf_renderer"]["renderer"] == "phase7_professional_pdf_renderer"
    assert manifest["human_mop_pdf_renderer"]["template_id"] == "bosgenesis_professional_mop_pdf"
    assert manifest["human_mop_pdf_renderer"]["page_count"] >= 1
    assert manifest["human_mop_pdf_renderer"]["overflow_count"] == 0
    assert manifest["mcp"]["sources_attempted"] == ["k8s_inspector_mcp", "helm_manager_mcp"]
    assert "Helm releases | 1" in human_mop
    assert "Raw Kubernetes resources | 2" in human_mop
    assert "release_name: api" in installation_notes
    assert "kind: Deployment" in installation_notes


def test_artifact_writer_uses_phase5_classification_for_safe_resource_lists(tmp_path) -> None:
    inventory = NormalizedInventory(
        source="postgres",
        namespace="bosgenesis",
        snapshot_id="run-123",
        run_id="run-123",
        resources=[
            InventoryResource(kind="Deployment", name="api", namespace="bosgenesis", source="k8s"),
            InventoryResource(kind="Secret", name="api-secret", namespace="bosgenesis", source="k8s"),
            InventoryResource(kind="Event", name="api-started", namespace="bosgenesis", source="k8s"),
        ],
    )
    classification = classify_inventory(inventory)

    result = LocalArtifactWriter(str(tmp_path)).write(
        mop_id="mop-123",
        run_id="run-abc",
        correlation_id="corr-abc",
        source_namespace="bosgenesis",
        request=MoPGenerationRequest(target_namespace="bosgenesis-copy-dev"),
        created_at=datetime(2026, 5, 28, tzinfo=UTC),
        warnings=classification.warnings if classification else [],
        inventory=inventory,
        classification=classification,
        snapshot_sources_attempted=["postgres"],
        mcp_sources_attempted=[],
    )

    manifest = json.loads(Path(result.artifact_manifest_path).read_text(encoding="utf-8"))
    installation_notes = Path(result.installation_notes_path).read_text(encoding="utf-8")

    assert manifest["artifact_type"] == "phase6_reconstruction_mop_artifact"
    assert manifest["classification"]["raw_k8s_count"] == 1
    assert manifest["classification"]["excluded_count"] == 1
    assert manifest["classification"]["warning_only_count"] == 1
    assert manifest["reconstruction"]["raw_manifest_count"] == 1
    assert "kind: Deployment" in installation_notes
    assert "kind: Secret" in installation_notes
    assert "raw_kubernetes_resources:\n  - kind: Deployment" in installation_notes
    assert "excluded_resources:\n  - kind: Secret" in installation_notes
    assert "kubectl apply -f generated/deployment-api.yaml" in installation_notes
    generated_manifest = Path(result.run_directory_path) / "generated" / "deployment-api.yaml"
    assert generated_manifest.is_file()
    assert "namespace: bosgenesis-copy-dev" in generated_manifest.read_text(encoding="utf-8")
    assert "api-started" not in installation_notes.split("raw_kubernetes_resources:", 1)[1].split(
        "application_targets:",
        1,
    )[0]


def test_phase8_installation_notes_expose_machine_readable_execution_plan(tmp_path) -> None:
    inventory = NormalizedInventory(
        source="postgres",
        namespace="bosgenesis",
        snapshot_id="run-123",
        run_id="run-123",
        resources=[
            InventoryResource(
                kind="ConfigMap",
                name="api-config",
                namespace="bosgenesis",
                source="k8s",
                normalized_payload={
                    "apiVersion": "v1",
                    "kind": "ConfigMap",
                    "metadata": {"name": "api-config", "namespace": "bosgenesis"},
                    "data": {"MODE": "test"},
                },
            ),
            InventoryResource(
                kind="Deployment",
                name="api",
                namespace="bosgenesis",
                source="k8s",
                normalized_payload={
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": "api", "namespace": "bosgenesis"},
                    "spec": {
                        "selector": {"matchLabels": {"app": "api"}},
                        "template": {
                            "metadata": {"labels": {"app": "api"}},
                            "spec": {"containers": [{"name": "api", "image": "example/api:1"}]},
                        },
                    },
                },
            ),
            InventoryResource(kind="Secret", name="api-secret", namespace="bosgenesis", source="k8s"),
        ],
        helm_releases=[
            InventoryHelmRelease(
                release_name="api",
                namespace="bosgenesis",
                chart_name="example/api",
                status="deployed",
                normalized_payload={"values": {"replicaCount": 1}},
            )
        ],
    )
    classification = classify_inventory(inventory)

    result = LocalArtifactWriter(str(tmp_path)).write(
        mop_id="mop-123",
        run_id="run-abc",
        correlation_id="corr-abc",
        source_namespace="bosgenesis",
        request=MoPGenerationRequest(target_namespace="bosgenesis-copy-dev"),
        created_at=datetime(2026, 5, 28, tzinfo=UTC),
        warnings=[],
        inventory=inventory,
        classification=classification,
        snapshot_sources_attempted=["postgres"],
        mcp_sources_attempted=["k8s_inspector_mcp", "helm_manager_mcp"],
    )

    installation_notes = Path(result.installation_notes_path).read_text(encoding="utf-8")
    plan = _extract_machine_execution_plan(installation_notes)
    machine_plan_path = Path(result.run_directory_path) / "machine_execution_plan.yaml"
    machine_plan_file = machine_plan_path.read_text(encoding="utf-8")
    standalone_plan = yaml.safe_load(machine_plan_file)
    machine_plan = plan["machine_execution_plan"]
    phases = machine_plan["phases"]
    phase_ids = [phase["phase_id"] for phase in phases]

    assert "&id" not in installation_notes
    assert "*id" not in installation_notes
    assert standalone_plan == plan
    assert machine_plan["executor_contract"]["parse_this_block_first"] is True
    assert machine_plan["executor_contract"]["dry_run_before_mutation"] is True
    assert phase_ids == [
        "verify_access",
        "prepare_target_namespace",
        "prepare_secret_placeholders",
        "apply_configmaps",
        "apply_pvcs",
        "install_helm_releases",
        "apply_raw_kubernetes_resources",
        "apply_ingress",
        "apply_application_metadata",
        "validate",
    ]
    assert machine_plan["dependency_graph"][5] == {
        "phase_id": "install_helm_releases",
        "depends_on": ["apply_configmaps", "apply_pvcs", "prepare_secret_placeholders"],
    }
    assert machine_plan["required_human_inputs"] == [
        {
            "input_id": "approved_secret_material_for_api-secret",
            "target": "Secret/api-secret",
            "reason": "Secret values are excluded and must be supplied from an approved secure source.",
            "blocks_phase": "prepare_secret_placeholders",
        }
    ]

    helm_steps = phases[5]["steps"]
    raw_steps = phases[6]["steps"]
    assert helm_steps[0]["type"] == "helm"
    assert [command["kind"] for command in helm_steps[0]["commands"]] == [
        "dry_run",
        "apply",
        "validate",
    ]
    assert helm_steps[0]["inference"]["label"] == "observed"
    assert raw_steps[0]["title"] == "Apply Deployment api"
    assert raw_steps[0]["requires_human_approval"] is True
    assert raw_steps[0]["commands"][0]["command"].endswith("--dry-run=server -o yaml")

    manifest = json.loads(Path(result.artifact_manifest_path).read_text(encoding="utf-8"))
    assert manifest["machine_execution_plan"]["machine_execution_plan"]["schema_version"] == "1.0"
    assert manifest["artifacts"]["machine_execution_plan_path"].endswith("machine_execution_plan.yaml")


def _extract_machine_execution_plan(installation_notes: str) -> dict:
    marker = "## 7. Machine Execution Plan"
    start = installation_notes.index(marker)
    yaml_start = installation_notes.index("```yaml", start) + len("```yaml")
    yaml_end = installation_notes.index("```", yaml_start)
    return yaml.safe_load(installation_notes[yaml_start:yaml_end])
