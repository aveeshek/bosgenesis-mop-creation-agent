from pathlib import Path

import yaml

from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.reconstruction.helm_values import redacted_values_yaml
from bosgenesis_mop_creation_agent.reconstruction.manifest_normalizer import (
    dump_manifest,
    normalize_manifest,
)
from bosgenesis_mop_creation_agent.reconstruction.planner import build_reconstruction_plan
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)


def test_phase6_manifest_normalizer_rewrites_namespace_and_removes_runtime_metadata() -> None:
    resource = InventoryResource(
        kind="Service",
        name="api",
        namespace="bosgenesis",
        source="test",
        normalized_payload={
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "api",
                "namespace": "bosgenesis",
                "uid": "runtime-uid",
                "resourceVersion": "123",
                "managedFields": [{"manager": "kube"}],
                "annotations": {
                    "kubectl.kubernetes.io/last-applied-configuration": "{}",
                    "keep": "yes",
                },
            },
        "spec": {
                "type": "ClusterIP",
                "clusterIP": "10.1.2.3",
                "selector": {"app": "api"},
                "ports": [{"port": 80}],
                "env": [{"name": "API_TOKEN", "value": "clear-token"}],
            },
            "status": {"loadBalancer": {}},
        },
    )

    manifest, warnings = normalize_manifest(resource, "target-ns")
    text = dump_manifest(manifest)

    assert warnings == []
    assert manifest["metadata"]["namespace"] == "target-ns"
    assert "uid" not in manifest["metadata"]
    assert "resourceVersion" not in manifest["metadata"]
    assert "managedFields" not in manifest["metadata"]
    assert "status" not in manifest
    assert "clusterIP" not in manifest["spec"]
    assert "clear-token" not in text
    assert "<REDACTED_PROVIDE_APPROVED_VALUE>" in text
    assert yaml.safe_load(text)["metadata"]["annotations"] == {"keep": "yes"}


def test_phase6_manifest_normalizer_strips_pvc_binding_runtime_state() -> None:
    resource = InventoryResource(
        kind="PersistentVolumeClaim",
        name="signoz-db-signoz-0",
        namespace="signoz",
        source="test",
        normalized_payload={
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": "signoz-db-signoz-0",
                "namespace": "signoz",
                "annotations": {
                    "pv.kubernetes.io/bind-completed": "yes",
                    "pv.kubernetes.io/bound-by-controller": "yes",
                    "volume.beta.kubernetes.io/storage-provisioner": "rancher.io/local-path",
                    "volume.kubernetes.io/selected-node": "ckit2cpubm1",
                    "volume.kubernetes.io/storage-provisioner": "rancher.io/local-path",
                    "bosgenesis.io/keep": "yes",
                },
            },
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": "1Gi"}},
                "storageClassName": "local-path",
                "volumeName": "pvc-source-runtime-value",
            },
            "status": {"phase": "Bound"},
        },
    )

    manifest, warnings = normalize_manifest(resource, "agent-testing")

    assert warnings == []
    assert manifest["metadata"]["namespace"] == "agent-testing"
    assert manifest["metadata"]["annotations"] == {"bosgenesis.io/keep": "yes"}
    assert "volumeName" not in manifest["spec"]
    assert "status" not in manifest


def test_phase6_helm_values_are_redacted() -> None:
    release = InventoryHelmRelease(
        release_name="api",
        namespace="bosgenesis",
        normalized_payload={
            "values": {
                "replicaCount": 2,
                "password": "clear-text",
                "nested": {"apiToken": "token-value", "normal": "kept"},
            }
        },
    )

    text = redacted_values_yaml(release)

    assert "clear-text" not in text
    assert "token-value" not in text
    assert "<REDACTED_PROVIDE_APPROVED_VALUE>" in text
    assert "normal: kept" in text


def test_phase6_planner_writes_raw_manifests_and_helm_values(tmp_path: Path) -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="bosgenesis",
        snapshot_id="snapshot-1",
        resources=[
            InventoryResource(
                kind="ConfigMap",
                name="api-config",
                namespace="bosgenesis",
                source="test",
                normalized_payload={
                    "apiVersion": "v1",
                    "kind": "ConfigMap",
                    "metadata": {"name": "api-config", "namespace": "bosgenesis"},
                    "data": {"MODE": "test"},
                },
            )
        ],
        helm_releases=[
            InventoryHelmRelease(
                release_name="api",
                namespace="bosgenesis",
                chart_name="example/api",
                normalized_payload={"values": {"password": "clear-text"}},
            )
        ],
    )
    classification = classify_inventory(inventory)

    plan = build_reconstruction_plan(
        inventory=inventory,
        classification=classification,
        target_namespace="target-ns",
        generated_dir=tmp_path / "generated",
        values_dir=tmp_path / "values",
    )

    assert plan.raw_manifest_count == 1
    assert plan.helm_release_count == 1
    raw_plan = plan.raw_manifests[0]
    helm_plan = plan.helm_releases[0]
    assert Path(raw_plan.file_path).is_file()
    assert Path(helm_plan.values_file_path).is_file()
    assert "namespace: target-ns" in Path(raw_plan.file_path).read_text(encoding="utf-8")
    assert "clear-text" not in Path(helm_plan.values_file_path).read_text(encoding="utf-8")
    assert helm_plan.source_release_name == "api"
    assert helm_plan.release_name == "agent-ai-api"
    assert raw_plan.dry_run_command == (
        "kubectl apply -f generated/configmap-api-config.yaml -n target-ns "
        "--dry-run=server -o yaml"
    )
    assert helm_plan.dry_run_command == (
        "helm upgrade --install agent-ai-api example/api --namespace target-ns "
        "--create-namespace -f values/values-agent-ai-api.yaml --dry-run"
    )


def test_phase6_planner_reconstructs_source_ingress_with_agent_generated_name(
    tmp_path: Path,
) -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="signoz",
        snapshot_id="snapshot-1",
        resources=[
            InventoryResource(
                kind="Ingress",
                name="signoz",
                namespace="signoz",
                source="test",
                normalized_payload={
                    "apiVersion": "networking.k8s.io/v1",
                    "kind": "Ingress",
                    "metadata": {
                        "name": "signoz",
                        "namespace": "signoz",
                        "resourceVersion": "runtime-value",
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
            )
        ],
    )
    classification = classify_inventory(inventory)

    plan = build_reconstruction_plan(
        inventory=inventory,
        classification=classification,
        target_namespace="agent-testing",
        generated_dir=tmp_path / "generated",
        values_dir=tmp_path / "values",
    )

    assert plan.raw_manifest_count == 1
    raw_plan = plan.raw_manifests[0]
    manifest = yaml.safe_load(Path(raw_plan.file_path).read_text(encoding="utf-8"))
    assert raw_plan.kind == "Ingress"
    assert raw_plan.name == "agent-ai-signoz"
    assert raw_plan.relative_path == "generated/ingress-agent-ai-signoz.yaml"
    assert raw_plan.validation_command == (
        "kubectl get ingress agent-ai-signoz -n agent-testing -o wide"
    )
    assert manifest["metadata"]["name"] == "agent-ai-signoz"
    assert manifest["metadata"]["namespace"] == "agent-testing"
    assert manifest["metadata"]["annotations"] == {
        "bosgenesis.io/generated-by": "bosgenesis-mop-creation-agent",
        "bosgenesis.io/original-name": "signoz",
    }
    assert "resourceVersion" not in manifest["metadata"]
    assert "ingress_name_prefixed_from:signoz" in raw_plan.warnings


def test_phase6_planner_uses_operator_target_release_name_hint(tmp_path: Path) -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="signoz",
        snapshot_id="snapshot-1",
        helm_releases=[
            InventoryHelmRelease(
                release_name="signoz",
                namespace="signoz",
                chart_name="signoz/signoz",
                normalized_payload={
                    "operator_chart_hint": {
                        "target_release_name": "demo-ai-signoz",
                    },
                },
            )
        ],
    )
    classification = classify_inventory(inventory)

    plan = build_reconstruction_plan(
        inventory=inventory,
        classification=classification,
        target_namespace="agent-testing",
        generated_dir=tmp_path / "generated",
        values_dir=tmp_path / "values",
    )

    helm_plan = plan.helm_releases[0]
    assert helm_plan.source_release_name == "signoz"
    assert helm_plan.release_name == "agent-ai-demo-ai-signoz"
    assert "agent-ai-demo-ai-signoz signoz/signoz" in helm_plan.install_command


def test_phase6_planner_reconstructs_helm_managed_source_ingress_with_agent_prefix(
    tmp_path: Path,
) -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="signoz",
        snapshot_id="snapshot-1",
        resources=[
            InventoryResource(
                kind="Ingress",
                name="signoz-ui",
                namespace="signoz",
                source="test",
                normalized_payload={
                    "apiVersion": "networking.k8s.io/v1",
                    "kind": "Ingress",
                    "metadata": {
                        "name": "signoz-ui",
                        "namespace": "signoz",
                        "labels": {"app.kubernetes.io/managed-by": "Helm"},
                        "annotations": {
                            "meta.helm.sh/release-name": "signoz",
                            "meta.helm.sh/release-namespace": "signoz",
                        },
                    },
                    "spec": {
                        "rules": [
                            {
                                "host": "signoz.bosgenesis.local",
                                "http": {"paths": []},
                            }
                        ]
                    },
                },
            )
        ],
        helm_releases=[
            InventoryHelmRelease(
                release_name="signoz",
                namespace="signoz",
                chart_name="signoz/signoz",
            )
        ],
    )
    classification = classify_inventory(inventory)

    plan = build_reconstruction_plan(
        inventory=inventory,
        classification=classification,
        target_namespace="agent-testing",
        generated_dir=tmp_path / "generated",
        values_dir=tmp_path / "values",
    )

    ingress_plans = [raw_plan for raw_plan in plan.raw_manifests if raw_plan.kind == "Ingress"]
    assert ingress_plans
    assert ingress_plans[0].name == "agent-ai-signoz-ui"
    assert "ingress_reconstructed_from_helm_managed_source" in ingress_plans[0].warnings
    assert Path(
        tmp_path / "generated" / "ingress-agent-ai-signoz-ui.yaml"
    ).is_file()


def test_phase6_planner_does_not_generate_ingress_when_source_has_none(
    tmp_path: Path,
) -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="signoz",
        snapshot_id="snapshot-1",
        resources=[
            InventoryResource(
                kind="ConfigMap",
                name="signoz-config",
                namespace="signoz",
                source="test",
                normalized_payload={
                    "apiVersion": "v1",
                    "kind": "ConfigMap",
                    "metadata": {"name": "signoz-config", "namespace": "signoz"},
                    "data": {"MODE": "test"},
                },
            )
        ],
    )
    classification = classify_inventory(inventory)

    plan = build_reconstruction_plan(
        inventory=inventory,
        classification=classification,
        target_namespace="agent-testing",
        generated_dir=tmp_path / "generated",
        values_dir=tmp_path / "values",
    )

    assert all(raw_plan.kind != "Ingress" for raw_plan in plan.raw_manifests)
    assert not list((tmp_path / "generated").glob("ingress-*.yaml"))
