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
    assert raw_plan.dry_run_command == (
        "kubectl apply -f generated/configmap-api-config.yaml -n target-ns "
        "--dry-run=server -o yaml"
    )
    assert helm_plan.dry_run_command == (
        "helm upgrade --install api example/api --namespace target-ns "
        "--create-namespace -f values/values-api.yaml --dry-run"
    )
