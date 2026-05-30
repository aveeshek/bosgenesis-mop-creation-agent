from bosgenesis_mop_creation_agent.classification.models import ResourceCategory
from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)


def _resource(
    kind: str,
    name: str,
    namespace: str = "bosgenesis",
    payload: dict | None = None,
) -> InventoryResource:
    return InventoryResource(
        kind=kind,
        name=name,
        namespace=namespace,
        source="test",
        normalized_payload=payload or {},
    )


def test_phase5_detects_helm_managed_resources_from_helm_metadata() -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="bosgenesis",
        snapshot_id="snapshot-1",
        resources=[
            _resource(
                "Deployment",
                "api",
                payload={
                    "metadata": {
                        "labels": {"app.kubernetes.io/managed-by": "Helm"},
                        "annotations": {
                            "meta.helm.sh/release-name": "api",
                            "meta.helm.sh/release-namespace": "bosgenesis",
                        },
                    }
                },
            )
        ],
        helm_releases=[InventoryHelmRelease(release_name="api", namespace="bosgenesis")],
    )

    result = classify_inventory(inventory)

    assert result is not None
    assert result.helm_managed_count == 1
    classified = result.resources[0]
    assert classified.category == ResourceCategory.HELM_MANAGED
    assert classified.helm_release_name == "api"
    assert "annotation:meta.helm.sh/release-name=api" in classified.evidence


def test_phase5_classifies_raw_excluded_and_warning_only_resources() -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="bosgenesis",
        snapshot_id="snapshot-1",
        resources=[
            _resource("Deployment", "raw-api"),
            _resource("Service", "raw-api"),
            _resource("Secret", "raw-secret"),
            _resource("ClusterRole", "cluster-role"),
            _resource("Deployment", "other-api", namespace="other"),
            _resource("Event", "api-started"),
        ],
    )

    result = classify_inventory(inventory)

    assert result is not None
    by_name = {item.resource.name: item for item in result.resources}
    assert by_name["raw-api"].category == ResourceCategory.RAW_K8S
    assert by_name["raw-secret"].category == ResourceCategory.EXCLUDED
    assert by_name["cluster-role"].category == ResourceCategory.EXCLUDED
    assert by_name["other-api"].category == ResourceCategory.EXCLUDED
    assert by_name["api-started"].category == ResourceCategory.WARNING_ONLY
    assert result.raw_k8s_count == 2
    assert result.excluded_count == 3
    assert result.warning_only_count == 1
    assert result.warnings == [
        "manual_review_required:Event/api-started:unsupported_namespaced_resource_manual_note"
    ]


def test_phase5_detects_helm_managed_resources_from_release_manifest() -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="bosgenesis",
        snapshot_id="snapshot-1",
        resources=[_resource("Service", "api")],
        helm_releases=[
            InventoryHelmRelease(
                release_name="api",
                namespace="bosgenesis",
                normalized_payload={
                    "manifest": {
                        "manifest": (
                            "apiVersion: v1\n"
                            "kind: Service\n"
                            "metadata:\n"
                            "  name: api\n"
                            "  namespace: bosgenesis\n"
                        )
                    }
                },
            )
        ],
    )

    result = classify_inventory(inventory)

    assert result is not None
    assert result.helm_managed_count == 1
    assert result.raw_k8s_count == 0
    classified = result.resources[0]
    assert classified.category == ResourceCategory.HELM_MANAGED
    assert classified.reason == "helm_manifest_membership_detected"
    assert classified.helm_release_name == "api"


def test_phase5_detects_helm_manifest_from_helm_manager_output_payload() -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="bosgenesis",
        snapshot_id="snapshot-1",
        resources=[
            _resource("Deployment", "agent-api"),
            _resource("Secret", "agent-api-secret"),
        ],
        helm_releases=[
            InventoryHelmRelease(
                release_name="agent-api",
                namespace="bosgenesis",
                normalized_payload={
                    "mcp_live": {
                        "manifest": {
                            "status": "ok",
                            "output": (
                                "apiVersion: v1\n"
                                "kind: Secret\n"
                                "metadata:\n"
                                "  name: agent-api-secret\n"
                                "---\n"
                                "apiVersion: apps/v1\n"
                                "kind: Deployment\n"
                                "metadata:\n"
                                "  name: agent-api\n"
                            ),
                        }
                    }
                },
            )
        ],
    )

    result = classify_inventory(inventory)

    assert result is not None
    by_name = {item.resource.name: item for item in result.resources}
    assert by_name["agent-api"].category == ResourceCategory.HELM_MANAGED
    assert by_name["agent-api"].helm_release_name == "agent-api"
    assert by_name["agent-api-secret"].category == ResourceCategory.EXCLUDED
    assert result.helm_managed_count == 1
    assert result.excluded_count == 1


def test_phase5_summarizes_pod_warning_noise() -> None:
    inventory = NormalizedInventory(
        source="test",
        namespace="bosgenesis",
        snapshot_id="snapshot-1",
        resources=[
            _resource("Pod", "api-1"),
            _resource("Pod", "api-2"),
            _resource("Event", "api-started"),
        ],
    )

    result = classify_inventory(inventory)

    assert result is not None
    assert result.warning_only_count == 3
    assert result.warnings == [
        "manual_review_required:Pod:2_runtime_artifacts_skipped",
        "manual_review_required:Event/api-started:unsupported_namespaced_resource_manual_note",
    ]
