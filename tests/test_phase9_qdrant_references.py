import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from bosgenesis_mop_creation_agent.api.app import create_app
from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.config.settings import (
    AgentSettings,
    QdrantRetrievalSettings,
    RetrievalSettings,
    Settings,
)
from bosgenesis_mop_creation_agent.retrieval.component_query_builder import build_component_queries
from bosgenesis_mop_creation_agent.retrieval.models import (
    ComponentIdentity,
    ReferenceCitation,
    ReferenceLookupResult,
)
from bosgenesis_mop_creation_agent.retrieval.reference_lookup import ReferenceLookupService
from bosgenesis_mop_creation_agent.retrieval.qdrant_client import QdrantClientError
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryResource,
    NormalizedInventory,
)


def test_qdrant_lookup_disabled_by_default() -> None:
    result = ReferenceLookupService(QdrantRetrievalSettings()).lookup(
        inventory=_inventory(),
        classification=classify_inventory(_inventory()),
    )

    assert result.status == "disabled"
    assert result.reference_count == 0


def test_qdrant_lookup_unavailable_when_endpoint_fails() -> None:
    service = ReferenceLookupService(
        QdrantRetrievalSettings(enabled=True, endpoint="http://qdrant.test:6333"),
        client=_UnavailableQdrantClient(),
    )

    result = service.lookup(inventory=_inventory(), classification=classify_inventory(_inventory()))

    assert result.status == "unavailable"
    assert result.warnings


def test_qdrant_lookup_no_matching_component() -> None:
    service = ReferenceLookupService(
        QdrantRetrievalSettings(enabled=True, endpoint="http://qdrant.test:6333"),
        client=_FakeQdrantClient(points=[]),
    )

    result = service.lookup(inventory=_inventory(), classification=classify_inventory(_inventory()))

    assert result.status == "no_match"
    assert result.reference_count == 0
    assert result.warnings == ["qdrant_reference_not_found"]


def test_qdrant_lookup_seeded_match_returns_prior_reference_only_citation() -> None:
    service = ReferenceLookupService(
        QdrantRetrievalSettings(
            enabled=True,
            endpoint="http://qdrant.test:6333",
            collection="mop_installation_notes",
            min_score=0.72,
        ),
        client=_FakeQdrantClient(points=[_seeded_point()]),
    )

    result = service.lookup(inventory=_inventory(), classification=classify_inventory(_inventory()))

    assert result.status == "references_found"
    assert result.reference_count == 1
    citation = result.references[0]
    assert citation.citation_label == "prior_reference_only_not_current_fact"
    assert citation.source_mop_id == "prior-mop"
    assert "name" in citation.matched_fields
    assert "Secret" not in citation.excerpt


def test_generated_artifacts_cite_qdrant_reference_without_current_fact_claim(tmp_path: Path) -> None:
    settings = Settings(
        agent=AgentSettings(local_storage_path=str(tmp_path)),
        retrieval=RetrievalSettings(qdrant=QdrantRetrievalSettings(enabled=True)),
    )
    app = create_app(settings)
    app.state.orchestrator._reference_lookup = _SeededReferenceLookup()  # noqa: SLF001
    client = TestClient(app)

    response = client.post(
        "/mop-creation/generate",
        json={"target_namespace": "target-ns", "caller": "pytest", "return_content": True},
    )

    payload = _wait_for_generated(client, response.json()["mop_id"])
    assert payload["qdrant_lookup_status"] == "references_found"
    assert payload["qdrant_reference_count"] == 1

    manifest = json.loads(
        Path(payload["artifacts"]["artifact_manifest_path"]).read_text(encoding="utf-8")
    )
    notes = Path(payload["artifacts"]["installation_notes_path"]).read_text(encoding="utf-8")

    assert manifest["qdrant_prior_references"]["status"] == "references_found"
    assert manifest["machine_execution_plan"]["machine_execution_plan"]["prior_references"]
    assert "prior_reference_only_not_current_fact" in notes
    assert "Treat Qdrant references as prior guidance only" in notes


def test_qdrant_ingestion_api_requires_user_confirmation(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(agent=AgentSettings(local_storage_path=str(tmp_path)))))

    response = client.post(
        "/references/qdrant/ingest-mop",
        json={"mop_id": "missing", "confirm": False, "caller": "pytest"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "confirm_required"


def test_qdrant_ingestion_api_is_user_driven_and_not_called_by_generation(tmp_path: Path) -> None:
    settings = Settings(
        agent=AgentSettings(local_storage_path=str(tmp_path)),
        retrieval=RetrievalSettings(qdrant=QdrantRetrievalSettings(enabled=True)),
    )
    app = create_app(settings)
    lookup = _SeededReferenceLookup()
    app.state.orchestrator._reference_lookup = lookup  # noqa: SLF001
    client = TestClient(app)

    response = client.post(
        "/mop-creation/generate",
        json={"target_namespace": "target-ns", "caller": "pytest"},
    )
    payload = _wait_for_generated(client, response.json()["mop_id"])

    assert payload["status"] == "generated"
    assert lookup.ingest_called is False

    ingest_response = client.post(
        "/references/qdrant/ingest-mop",
        json={"mop_id": payload["mop_id"], "confirm": True, "caller": "pytest"},
    )

    assert ingest_response.status_code == 200
    assert ingest_response.json()["status"] == "ingested"
    assert lookup.ingest_called is True


def test_component_query_builder_extracts_exact_identity_terms() -> None:
    inventory = _inventory()
    queries = build_component_queries(inventory, classify_inventory(inventory))

    assert queries
    query = queries[0]
    assert query.component.kind == "Deployment"
    assert query.component.name == "orders-api"
    assert "orders-api" in query.exact_terms
    assert "registry.example.com/orders/api" in query.exact_terms


class _FakeQdrantClient:
    def __init__(self, points: list[dict[str, Any]]) -> None:
        self._points = points

    def search_component(self, query: Any) -> list[dict[str, Any]]:
        return self._points


class _UnavailableQdrantClient:
    def search_component(self, query: Any) -> list[dict[str, Any]]:
        raise QdrantClientError("connection_failed")


class _SeededReferenceLookup:
    def __init__(self) -> None:
        self.ingest_called = False

    def lookup(self, **_: Any) -> ReferenceLookupResult:
        return ReferenceLookupResult(
            enabled=True,
            status="references_found",
            references=[
                ReferenceCitation(
                    reference_id="prior-ref-1",
                    qdrant_collection="mop_installation_notes",
                    source_mop_id="prior-mop",
                    source_artifact_type="installation_notes",
                    source_namespace="prior-ns",
                    component_identity=ComponentIdentity(kind="Deployment", name="orders-api"),
                    matched_fields=["kind", "name"],
                    score=0.95,
                    confidence="high",
                    excerpt="Prior reference only: deployment recreation used generated manifest.",
                )
            ],
        )

    def ingest_mop_artifacts(self, **_: Any) -> dict[str, Any]:
        self.ingest_called = True
        return {
            "status": "ingested",
            "mop_id": "test-mop",
            "collection": "mop_installation_notes",
            "point_count": 1,
        }


def _wait_for_generated(client: TestClient, mop_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/mop-creation/{mop_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] != "accepted":
            return payload
        time.sleep(0.05)
    raise AssertionError("MoP generation did not complete")


def _inventory() -> NormalizedInventory:
    return NormalizedInventory(
        source="test",
        namespace="source-ns",
        snapshot_id="snapshot-1",
        resources=[
            InventoryResource(
                kind="Deployment",
                name="orders-api",
                namespace="source-ns",
                source="test",
                normalized_payload={
                    "metadata": {
                        "name": "orders-api",
                        "namespace": "source-ns",
                        "labels": {
                            "app.kubernetes.io/name": "orders",
                            "app.kubernetes.io/component": "api",
                        },
                    },
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {"name": "api", "image": "registry.example.com/orders/api:1.2.3"}
                                ]
                            }
                        }
                    },
                },
            )
        ],
    )


def _seeded_point() -> dict[str, Any]:
    return {
        "id": "prior-ref-1",
        "payload": {
            "mop_id": "prior-mop",
            "source_namespace": "prior-ns",
            "artifact_type": "installation_notes",
            "component": {
                "kind": "Deployment",
                "name": "orders-api",
                "labels": {"app.kubernetes.io/name": "orders"},
                "image_repositories": ["registry.example.com/orders/api"],
            },
            "text": "orders-api deployment was recreated from generated manifests. password=hidden",
        },
    }
