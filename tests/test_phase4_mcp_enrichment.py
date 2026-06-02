from bosgenesis_mop_creation_agent.config.settings import EndpointSettings
from bosgenesis_mop_creation_agent.mcp_clients.base import InMemoryMcpTransport, McpClientError
from bosgenesis_mop_creation_agent.mcp_clients.data_ingestion_client import DataIngestionClient
from bosgenesis_mop_creation_agent.mcp_clients.enrichment import McpEnrichmentService
from bosgenesis_mop_creation_agent.mcp_clients.helm_manager_client import HelmManagerClient
from bosgenesis_mop_creation_agent.mcp_clients.k8s_inspector_client import K8sInspectorClient
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)


def _endpoint() -> EndpointSettings:
    return EndpointSettings(enabled=True, endpoint="http://mcp.example.local/mcp")


def _service(transport: InMemoryMcpTransport) -> McpEnrichmentService:
    endpoint = _endpoint()
    return McpEnrichmentService(
        k8s_client=K8sInspectorClient.from_settings(endpoint, transport),
        helm_client=HelmManagerClient.from_settings(endpoint, transport),
        data_ingestion_client=DataIngestionClient.from_settings(endpoint, transport),
    )


def _detail_service(transport: InMemoryMcpTransport) -> McpEnrichmentService:
    from bosgenesis_mop_creation_agent.config.settings import K8sInspectorSettings

    endpoint = _endpoint()
    return McpEnrichmentService(
        k8s_client=K8sInspectorClient.from_settings(
            K8sInspectorSettings(
                enabled=True,
                endpoint="http://mcp.example.local/mcp",
            ),
            transport,
        ),
        helm_client=HelmManagerClient.from_settings(endpoint, transport),
        data_ingestion_client=DataIngestionClient.from_settings(endpoint, transport),
    )


def test_mcp_enrichment_builds_live_inventory_without_raw_cluster_tools() -> None:
    transport = InMemoryMcpTransport(
        responses={
            "k8s_list_deployments": {
                "items": [{"metadata": {"name": "mop-api"}, "namespace": "bosgenesis"}]
            },
            "k8s_get_resource": {
                "status": "ok",
                "resource": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": "mop-api", "namespace": "bosgenesis"},
                    "spec": {"replicas": 1},
                },
            },
            "helm_list_releases": {
                "releases": [
                    {
                        "name": "mop-api",
                        "namespace": "bosgenesis",
                        "chart": "bosgenesis/mop-api",
                    }
                ]
            },
            "helm_release_status": {"status": "deployed", "revision": 7},
            "helm_release_history": {"items": []},
            "helm_get_values": {"values": {"replicaCount": 1}},
            "helm_get_manifest": {"manifest": "apiVersion: apps/v1\nkind: Deployment\n"},
            "helm_repo_list": {"items": []},
            "data_ingestion_health": {"status": "ok"},
            "data_ingestion_latest_scan": {"status": "completed"},
        }
    )

    result = _service(transport).enrich(
        namespace="bosgenesis",
        correlation_id="phase4-test",
        snapshot_inventory=None,
    )

    assert result.inventory is not None
    assert result.inventory.resource_count == 1
    assert result.inventory.helm_release_count == 1
    assert result.inventory.helm_releases[0].normalized_payload["manifest"]["manifest"].startswith(
        "apiVersion: apps/v1"
    )
    assert result.sources_attempted == [
        "k8s_inspector_mcp",
        "helm_manager_mcp",
        "data_ingestion_mcp",
    ]
    called_tools = {call[1] for call in transport.calls}
    assert "tools/list" in called_tools
    assert "k8s_list_deployments" in called_tools
    assert "k8s_get_resource" in called_tools
    assert "helm_list_releases" in called_tools
    assert "kubectl" not in called_tools
    assert "helm" not in called_tools


def test_mcp_enrichment_merges_live_inventory_and_continues_after_dependency_failure() -> None:
    snapshot = NormalizedInventory(
        source="postgres",
        namespace="bosgenesis",
        snapshot_id="snapshot-1",
        resources=[
            InventoryResource(
                kind="ConfigMap",
                name="existing-config",
                namespace="bosgenesis",
                source="postgres",
            )
        ],
        helm_releases=[
            InventoryHelmRelease(
                release_name="mop-api",
                namespace="bosgenesis",
                chart_name="snapshot/chart",
                status="pending",
            )
        ],
    )
    transport = InMemoryMcpTransport(
        responses={
            "k8s_list_services": {
                "items": [{"metadata": {"name": "mop-api"}, "namespace": "bosgenesis"}]
            },
            "helm_list_releases": McpClientError("helm manager unavailable"),
            "data_ingestion_health": {"status": "ok"},
            "data_ingestion_latest_scan": {"status": "completed"},
        }
    )

    result = _service(transport).enrich(
        namespace="bosgenesis",
        correlation_id="phase4-test",
        snapshot_inventory=snapshot,
    )

    assert result.inventory is not None
    assert result.inventory.resource_count == 2
    assert result.inventory.helm_release_count == 1
    assert result.inventory.helm_releases[0].chart_name == "snapshot/chart"
    assert "helm manager unavailable" in " ".join(result.warnings)


def test_mcp_enrichment_skips_tools_that_are_not_advertised() -> None:
    transport = InMemoryMcpTransport(
        available_tools={
            "k8s_namespace_summary",
            "k8s_list_pods",
            "helm_list_releases",
            "data_ingestion_health",
        },
        responses={
            "k8s_namespace_summary": {"namespace": "bosgenesis"},
            "k8s_list_pods": {"items": [{"metadata": {"name": "api"}, "namespace": "bosgenesis"}]},
            "helm_list_releases": {"releases": []},
            "data_ingestion_health": {"status": "ok"},
        },
    )

    result = _service(transport).enrich(
        namespace="bosgenesis",
        correlation_id="phase4-test",
        snapshot_inventory=None,
    )

    called_tools = {call[1] for call in transport.calls}
    assert result.warnings == []
    assert "k8s_list_daemonsets" not in called_tools
    assert "k8s_list_configmaps" not in called_tools
    assert "data_ingestion_latest_scan" not in called_tools


def test_mcp_enrichment_fetches_full_resource_details_when_available() -> None:
    transport = InMemoryMcpTransport(
        responses={
            "k8s_list_deployments": {
                "items": [{"metadata": {"name": "api"}, "namespace": "bosgenesis"}]
            },
            "k8s_get_resource": {
                "status": "ok",
                "resource": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": "api", "namespace": "bosgenesis"},
                    "spec": {"replicas": 1},
                    "status": {"availableReplicas": 1},
                },
            },
            "helm_list_releases": {"releases": []},
            "data_ingestion_health": {"status": "ok"},
        }
    )

    result = _detail_service(transport).enrich(
        namespace="bosgenesis",
        correlation_id="phase61-test",
        snapshot_inventory=None,
    )

    assert result.inventory is not None
    assert result.inventory.resources[0].normalized_payload["spec"] == {"replicas": 1}
    called_tools = [call[1] for call in transport.calls]
    assert "k8s_get_resource" in called_tools


def test_mcp_enrichment_detail_mode_warns_when_tool_unavailable() -> None:
    transport = InMemoryMcpTransport(
        available_tools={"k8s_list_deployments", "helm_list_releases", "data_ingestion_health"},
        responses={
            "k8s_list_deployments": {
                "items": [{"metadata": {"name": "api"}, "namespace": "bosgenesis"}]
            },
            "helm_list_releases": {"releases": []},
            "data_ingestion_health": {"status": "ok"},
        },
    )

    result = _detail_service(transport).enrich(
        namespace="bosgenesis",
        correlation_id="phase61-test",
        snapshot_inventory=None,
    )

    assert "k8s_mcp_detail_enrichment_unavailable" in " ".join(result.warnings)
    called_tools = [call[1] for call in transport.calls]
    assert "k8s_get_resource" not in called_tools
