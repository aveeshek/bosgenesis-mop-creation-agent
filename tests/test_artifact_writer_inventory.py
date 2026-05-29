from datetime import UTC, datetime
import json
from pathlib import Path

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
    assert manifest["mcp"]["sources_attempted"] == ["k8s_inspector_mcp", "helm_manager_mcp"]
    assert "Helm releases | 1" in human_mop
    assert "Raw Kubernetes resources | 2" in human_mop
    assert "release_name: api" in installation_notes
    assert "kind: Deployment" in installation_notes
