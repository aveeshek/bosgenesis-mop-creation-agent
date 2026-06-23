from datetime import UTC, datetime
import json
from pathlib import Path

import yaml

from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.models.requests import (
    HelmChartHint,
    HelmChartSourceType,
    MoPGenerationRequest,
)
from bosgenesis_mop_creation_agent.rendering.artifact_writer import LocalArtifactWriter
from bosgenesis_mop_creation_agent.reconstruction.quality_gate import ReconstructionQualityError
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
    assert helm_steps[0]["type"] == "helm_upgrade"
    assert helm_steps[0]["release_name"] == "agent-ai-api"
    assert helm_steps[0]["source_release_name"] == "api"
    assert helm_steps[0]["chart_ref"] == "example/api"
    assert helm_steps[0]["values_refs"] == ["values/values-agent-ai-api.yaml"]
    assert helm_steps[0]["generated_by"] == "bosgenesis-mop-creation-agent"
    assert [command["kind"] for command in helm_steps[0]["commands"]] == [
        "dry_run",
        "apply",
        "validate",
    ]
    assert helm_steps[0]["inference"]["label"] == "observed"
    assert raw_steps[0]["title"] == "Apply Deployment api"
    assert raw_steps[0]["requires_human_approval"] is True
    assert raw_steps[0]["commands"][0]["command"].endswith("--dry-run=server -o yaml")
    helm_validate_steps = [
        step for step in phases[9]["steps"] if step["type"] == "helm_validate"
    ]
    assert helm_validate_steps[0]["release_name"] == "agent-ai-api"
    assert helm_validate_steps[0]["chart_ref"] == "example/api"
    assert helm_validate_steps[0]["values_refs"] == ["values/values-agent-ai-api.yaml"]
    assert helm_validate_steps[0]["commands"][0]["command"].startswith(
        "helm template agent-ai-api example/api"
    )

    manifest = json.loads(Path(result.artifact_manifest_path).read_text(encoding="utf-8"))
    assert manifest["machine_execution_plan"]["machine_execution_plan"]["schema_version"] == "1.0"
    assert manifest["artifacts"]["machine_execution_plan_path"].endswith("machine_execution_plan.yaml")


def test_artifact_writer_fails_closed_for_helm_managed_workload_without_release_plan(
    tmp_path,
) -> None:
    inventory = NormalizedInventory(
        source="mcp",
        namespace="signoz",
        snapshot_id="snapshot-1",
        run_id="run-123",
        resources=[
            InventoryResource(
                kind="Deployment",
                name="signoz-otel-collector",
                namespace="signoz",
                source="k8s",
                normalized_payload={
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {
                        "name": "signoz-otel-collector",
                        "namespace": "signoz",
                        "labels": {"app.kubernetes.io/managed-by": "Helm"},
                        "annotations": {
                            "meta.helm.sh/release-name": "signoz",
                            "meta.helm.sh/release-namespace": "signoz",
                        },
                    },
                    "spec": {
                        "selector": {"matchLabels": {"app": "otel"}},
                        "template": {
                            "metadata": {"labels": {"app": "otel"}},
                            "spec": {
                                "containers": [
                                    {
                                        "name": "otel",
                                        "image": "docker.io/signoz/signoz-otel-collector",
                                    }
                                ]
                            },
                        },
                    },
                },
            )
        ],
        helm_releases=[],
    )
    classification = classify_inventory(inventory)

    try:
        LocalArtifactWriter(str(tmp_path)).write(
            mop_id="mop-fail",
            run_id="run-abc",
            correlation_id="corr-abc",
            source_namespace="signoz",
            request=MoPGenerationRequest(target_namespace="agent-testing"),
            created_at=datetime(2026, 6, 20, tzinfo=UTC),
            warnings=[],
            inventory=inventory,
            classification=classification,
            snapshot_sources_attempted=[],
            mcp_sources_attempted=["k8s_inspector_mcp"],
        )
    except ReconstructionQualityError as exc:
        assert exc.code == "INCOMPLETE_HELM_WORKLOAD_RECONSTRUCTION"
        assert (
            "Deployment/signoz-otel-collector:helm_release_plan_missing:signoz"
            in exc.details
        )
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected Helm workload reconstruction failure")

    assert not (tmp_path / "mop-fail").exists()


def test_artifact_writer_uses_public_helm_chart_hint_for_missing_release_plan(tmp_path) -> None:
    inventory = NormalizedInventory(
        source="mcp",
        namespace="signoz",
        snapshot_id="snapshot-1",
        run_id="run-123",
        resources=[
            InventoryResource(
                kind="Deployment",
                name="signoz-otel-collector",
                namespace="signoz",
                source="k8s",
                normalized_payload={
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {
                        "name": "signoz-otel-collector",
                        "namespace": "signoz",
                        "labels": {"app.kubernetes.io/managed-by": "Helm"},
                        "annotations": {
                            "meta.helm.sh/release-name": "signoz",
                            "meta.helm.sh/release-namespace": "signoz",
                        },
                    },
                    "spec": {
                        "selector": {"matchLabels": {"app": "otel"}},
                        "template": {
                            "metadata": {"labels": {"app": "otel"}},
                            "spec": {
                                "containers": [
                                    {
                                        "name": "otel",
                                        "image": "docker.io/signoz/signoz-otel-collector",
                                    }
                                ]
                            },
                        },
                    },
                },
            )
        ],
        helm_releases=[],
    )
    classification = classify_inventory(inventory)

    result = LocalArtifactWriter(str(tmp_path)).write(
        mop_id="mop-hinted",
        run_id="run-abc",
        correlation_id="corr-abc",
        source_namespace="signoz",
        request=MoPGenerationRequest(
            target_namespace="agent-testing",
            helm_chart_hints=[
                HelmChartHint(
                    release_name="signoz",
                    chart_ref="signoz/signoz",
                    chart_version="0.73.0",
                    repo_name="signoz",
                    repo_url="https://charts.signoz.io",
                    source_type=HelmChartSourceType.PUBLIC,
                )
            ],
        ),
        created_at=datetime(2026, 6, 20, tzinfo=UTC),
        warnings=[],
        inventory=inventory,
        classification=classification,
        snapshot_sources_attempted=[],
        mcp_sources_attempted=["k8s_inspector_mcp"],
    )

    manifest = json.loads(Path(result.artifact_manifest_path).read_text(encoding="utf-8"))
    generated_values = manifest["reconstruction"]["generated_values"][0]
    installation_notes = Path(result.installation_notes_path).read_text(encoding="utf-8")
    human_mop = Path(result.human_mop_markdown_path).read_text(encoding="utf-8")
    machine_plan = yaml.safe_load(
        Path(result.run_directory_path, "machine_execution_plan.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result.reconstruction_helm_release_count == 1
    assert manifest["reconstruction"]["helm_release_count"] == 1
    assert generated_values["release_name"] == "agent-ai-signoz"
    assert generated_values["source_release_name"] == "signoz"
    assert generated_values["chart_ref"] == "signoz/signoz"
    assert generated_values["chart_version"] == "0.73.0"
    assert generated_values["chart_source"] == "public"
    assert generated_values["repo_url"] == "https://charts.signoz.io"
    assert "helm upgrade --install agent-ai-signoz signoz/signoz" in installation_notes
    assert "Executable Helm plans generated for releases: agent-ai-signoz" in human_mop
    assert "--version 0.73.0" in installation_notes
    assert "chart_source: public" in installation_notes
    helm_phase = machine_plan["machine_execution_plan"]["phases"][5]
    assert helm_phase["phase_id"] == "install_helm_releases"
    assert helm_phase["steps"][0]["required_human_inputs"] == []
    assert helm_phase["steps"][0]["release_name"] == "agent-ai-signoz"
    assert helm_phase["steps"][0]["source_release_name"] == "signoz"
    assert helm_phase["steps"][0]["chart_ref"] == "signoz/signoz"
    validate_phase = machine_plan["machine_execution_plan"]["phases"][9]
    helm_validate_steps = [
        step for step in validate_phase["steps"] if step["type"] == "helm_validate"
    ]
    assert helm_validate_steps[0]["release_name"] == "agent-ai-signoz"
    assert helm_validate_steps[0]["chart_ref"] == "signoz/signoz"
    assert helm_validate_steps[0]["values_refs"] == ["values/values-agent-ai-signoz.yaml"]


def test_artifact_writer_skips_helm_instance_pvcs_and_rewrites_ingress_backend(
    tmp_path,
) -> None:
    inventory = NormalizedInventory(
        source="mcp",
        namespace="signoz",
        snapshot_id="snapshot-1",
        run_id="run-123",
        resources=[
            InventoryResource(
                kind="Service",
                name="signoz",
                namespace="signoz",
                source="k8s",
                normalized_payload={
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {
                        "name": "signoz",
                        "namespace": "signoz",
                        "labels": {"app.kubernetes.io/instance": "signoz"},
                    },
                    "spec": {"ports": [{"port": 8080}], "selector": {"app": "signoz"}},
                },
            ),
            InventoryResource(
                kind="PersistentVolumeClaim",
                name="data-signoz-zookeeper-0",
                namespace="signoz",
                source="k8s",
                normalized_payload={
                    "apiVersion": "v1",
                    "kind": "PersistentVolumeClaim",
                    "metadata": {
                        "name": "data-signoz-zookeeper-0",
                        "namespace": "signoz",
                        "labels": {"app.kubernetes.io/instance": "signoz"},
                    },
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {"requests": {"storage": "8Gi"}},
                    },
                },
            ),
            InventoryResource(
                kind="Ingress",
                name="signoz",
                namespace="signoz",
                source="k8s",
                normalized_payload={
                    "apiVersion": "networking.k8s.io/v1",
                    "kind": "Ingress",
                    "metadata": {
                        "name": "signoz",
                        "namespace": "signoz",
                        "labels": {"app.kubernetes.io/instance": "signoz"},
                    },
                    "spec": {
                        "rules": [
                            {
                                "host": "signoz.bosgenesis.local",
                                "http": {
                                    "paths": [
                                        {
                                            "path": "/",
                                            "pathType": "Prefix",
                                            "backend": {
                                                "service": {
                                                    "name": "signoz",
                                                    "port": {"number": 8080},
                                                }
                                            },
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
            ),
        ],
        helm_releases=[
            InventoryHelmRelease(
                release_name="signoz",
                namespace="signoz",
                chart_name="signoz/signoz",
                chart_version="0.129.0",
                status="deployed",
                normalized_payload={"values": {}},
            )
        ],
    )
    classification = classify_inventory(inventory)

    result = LocalArtifactWriter(str(tmp_path)).write(
        mop_id="mop-ingress-rewrite",
        run_id="run-abc",
        correlation_id="corr-abc",
        source_namespace="signoz",
        request=MoPGenerationRequest(target_namespace="agent-testing"),
        created_at=datetime(2026, 6, 23, tzinfo=UTC),
        warnings=[],
        inventory=inventory,
        classification=classification,
        snapshot_sources_attempted=[],
        mcp_sources_attempted=["k8s_inspector_mcp", "helm_manager_mcp"],
    )

    manifest = json.loads(Path(result.artifact_manifest_path).read_text(encoding="utf-8"))
    generated_manifest = yaml.safe_load(
        Path(result.run_directory_path, "generated", "ingress-agent-ai-signoz.yaml").read_text(
            encoding="utf-8"
        )
    )
    machine_plan = yaml.safe_load(
        Path(result.run_directory_path, "machine_execution_plan.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert result.reconstruction_raw_manifest_count == 1
    assert manifest["classification"]["helm_managed_count"] == 3
    assert manifest["classification"]["raw_k8s_count"] == 0
    assert manifest["reconstruction"]["raw_manifest_count"] == 1
    assert not Path(
        result.run_directory_path,
        "generated",
        "persistentvolumeclaim-data-signoz-zookeeper-0.yaml",
    ).exists()
    backend_service = generated_manifest["spec"]["rules"][0]["http"]["paths"][0][
        "backend"
    ]["service"]
    assert generated_manifest["metadata"]["name"] == "agent-ai-signoz"
    assert backend_service["name"] == "agent-ai-signoz"
    ingress_steps = machine_plan["machine_execution_plan"]["phases"][7]["steps"]
    assert ingress_steps[0]["manifest_refs"] == ["generated/ingress-agent-ai-signoz.yaml"]
    assert any(
        "ingress_backend_service_rewritten:signoz->agent-ai-signoz" in warning
        for warning in manifest["reconstruction"]["generated_manifests"][0]["warnings"]
    )

def test_artifact_writer_fails_closed_for_private_chart_hint_without_repo_url(
    tmp_path,
) -> None:
    inventory = NormalizedInventory(
        source="mcp",
        namespace="signoz",
        snapshot_id="snapshot-1",
        run_id="run-123",
        resources=[
            InventoryResource(
                kind="Service",
                name="signoz",
                namespace="signoz",
                source="k8s",
                normalized_payload={
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {
                        "name": "signoz",
                        "namespace": "signoz",
                        "annotations": {
                            "meta.helm.sh/release-name": "signoz",
                            "meta.helm.sh/release-namespace": "signoz",
                        },
                    },
                    "spec": {"ports": [{"port": 8080}], "selector": {"app": "signoz"}},
                },
            )
        ],
        helm_releases=[],
    )
    classification = classify_inventory(inventory)

    try:
        LocalArtifactWriter(str(tmp_path)).write(
            mop_id="mop-private-missing-repo",
            run_id="run-abc",
            correlation_id="corr-abc",
            source_namespace="signoz",
            request=MoPGenerationRequest(
                target_namespace="agent-testing",
                helm_chart_hints=[
                    HelmChartHint(
                        release_name="signoz",
                        chart_ref="private/signoz",
                        source_type=HelmChartSourceType.PRIVATE,
                    )
                ],
            ),
            created_at=datetime(2026, 6, 20, tzinfo=UTC),
            warnings=[],
            inventory=inventory,
            classification=classification,
            snapshot_sources_attempted=[],
            mcp_sources_attempted=["k8s_inspector_mcp"],
        )
    except ReconstructionQualityError as exc:
        assert exc.code == "INCOMPLETE_HELM_WORKLOAD_RECONSTRUCTION"
        assert "HelmRelease/signoz:private_repo_url_required" in exc.details
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected private repo URL failure")

    assert not (tmp_path / "mop-private-missing-repo").exists()


def test_artifact_writer_fails_closed_for_missing_helm_chart_ref(tmp_path) -> None:
    inventory = NormalizedInventory(
        source="mcp",
        namespace="signoz",
        snapshot_id="snapshot-1",
        run_id="run-123",
        resources=[
            InventoryResource(
                kind="Service",
                name="signoz",
                namespace="signoz",
                source="k8s",
                normalized_payload={
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {
                        "name": "signoz",
                        "namespace": "signoz",
                        "annotations": {
                            "meta.helm.sh/release-name": "signoz",
                            "meta.helm.sh/release-namespace": "signoz",
                        },
                    },
                    "spec": {"ports": [{"port": 8080}], "selector": {"app": "signoz"}},
                },
            )
        ],
        helm_releases=[
            InventoryHelmRelease(
                release_name="signoz",
                namespace="signoz",
                chart_name=None,
                status="deployed",
                normalized_payload={"values": {"replicaCount": 1}},
            )
        ],
    )
    classification = classify_inventory(inventory)

    try:
        LocalArtifactWriter(str(tmp_path)).write(
            mop_id="mop-missing-chart",
            run_id="run-abc",
            correlation_id="corr-abc",
            source_namespace="signoz",
            request=MoPGenerationRequest(target_namespace="agent-testing"),
            created_at=datetime(2026, 6, 20, tzinfo=UTC),
            warnings=[],
            inventory=inventory,
            classification=classification,
            snapshot_sources_attempted=[],
            mcp_sources_attempted=["k8s_inspector_mcp", "helm_manager_mcp"],
        )
    except ReconstructionQualityError as exc:
        assert exc.code == "INCOMPLETE_HELM_WORKLOAD_RECONSTRUCTION"
        assert "HelmRelease/signoz:chart_ref_missing" in exc.details
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected missing Helm chart reference failure")

    assert not (tmp_path / "mop-missing-chart").exists()


def _extract_machine_execution_plan(installation_notes: str) -> dict:
    marker = "## 7. Machine Execution Plan"
    start = installation_notes.index(marker)
    yaml_start = installation_notes.index("```yaml", start) + len("```yaml")
    yaml_end = installation_notes.index("```", yaml_start)
    return yaml.safe_load(installation_notes[yaml_start:yaml_end])
