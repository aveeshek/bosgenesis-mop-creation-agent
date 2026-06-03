from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid5, NAMESPACE_URL

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.config.settings import QdrantRetrievalSettings
from bosgenesis_mop_creation_agent.retrieval.component_query_builder import build_component_queries
from bosgenesis_mop_creation_agent.retrieval.models import (
    ComponentIdentity,
    ComponentQuery,
    QdrantPointPayload,
    ReferenceCitation,
    ReferenceLookupResult,
)
from bosgenesis_mop_creation_agent.retrieval.qdrant_client import (
    QdrantClientError,
    QdrantReadOnlyClient,
)
from bosgenesis_mop_creation_agent.sources.snapshot_models import NormalizedInventory


class ReferenceLookupService:
    def __init__(
        self,
        settings: QdrantRetrievalSettings,
        client: QdrantReadOnlyClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or QdrantReadOnlyClient(settings)

    def lookup(
        self,
        *,
        inventory: NormalizedInventory | None,
        classification: ClassificationSummary | None,
    ) -> ReferenceLookupResult:
        if not self._settings.enabled:
            return ReferenceLookupResult(enabled=False, status="disabled")
        if self._settings.mode != "read_only":
            return ReferenceLookupResult(
                enabled=False,
                status="disabled_non_read_only_mode",
                warnings=["qdrant_lookup_disabled:mode_is_not_read_only"],
            )
        if not self._settings.endpoint:
            return ReferenceLookupResult(
                enabled=True,
                status="unavailable",
                warnings=["qdrant_lookup_unavailable:endpoint_missing"],
            )

        queries = build_component_queries(inventory, classification)
        if not queries:
            return ReferenceLookupResult(enabled=True, status="no_query", queries=[])

        accepted: dict[str, ReferenceCitation] = {}
        warnings: list[str] = []
        try:
            for query in queries:
                for point in self._client.search_component(query):
                    citation = _citation_from_point(
                        point,
                        query=query,
                        collection=self._settings.collection,
                        min_score=self._settings.min_score,
                        exact_match_bonus=self._settings.exact_match_bonus,
                    )
                    if citation is None:
                        continue
                    existing = accepted.get(citation.reference_id)
                    if existing is None or citation.score > existing.score:
                        accepted[citation.reference_id] = citation
        except QdrantClientError as exc:
            return ReferenceLookupResult(
                enabled=True,
                status="unavailable",
                queries=queries,
                warnings=[f"qdrant_lookup_unavailable:{exc}"],
            )

        references = sorted(accepted.values(), key=lambda item: item.score, reverse=True)[
            : self._settings.top_k
        ]
        if not references:
            warnings.append("qdrant_reference_not_found")
            return ReferenceLookupResult(
                enabled=True,
                status="no_match",
                queries=queries,
                warnings=warnings,
            )
        return ReferenceLookupResult(
            enabled=True,
            status="references_found",
            references=references,
            queries=queries,
            warnings=warnings,
        )

    def ingest_mop_artifacts(self, *, mop_id: str, run_directory: Path) -> dict[str, Any]:
        if not self._settings.ingestion_api_enabled:
            return {
                "status": "disabled",
                "mop_id": mop_id,
                "error": "qdrant_ingestion_api_disabled",
            }
        if not self._settings.endpoint:
            return {
                "status": "unavailable",
                "mop_id": mop_id,
                "error": "qdrant_endpoint_missing",
            }
        points = build_ingestion_points(
            mop_id=mop_id,
            run_directory=run_directory,
            max_bytes=self._settings.max_ingestion_artifact_bytes,
        )
        if not points:
            return {"status": "no_artifacts", "mop_id": mop_id, "point_count": 0}
        try:
            response = self._client.upsert_points(points)
        except QdrantClientError as exc:
            return {
                "status": "unavailable",
                "mop_id": mop_id,
                "error": str(exc),
                "point_count": len(points),
            }
        return {
            "status": "ingested",
            "mop_id": mop_id,
            "collection": self._settings.collection,
            "point_count": len(points),
            "qdrant_response": response,
        }


def build_ingestion_points(
    *,
    mop_id: str,
    run_directory: Path,
    max_bytes: int,
) -> list[QdrantPointPayload]:
    manifest_path = run_directory / "artifact.json"
    manifest = _read_json(manifest_path)
    source_namespace = manifest.get("source_namespace") if isinstance(manifest, dict) else None
    component_payloads = _component_payloads(manifest)
    artifact_paths = [
        *run_directory.glob("*.installation.md"),
        *run_directory.glob("*.human-mop.md"),
        run_directory / "machine_execution_plan.yaml",
    ]
    points: list[QdrantPointPayload] = []
    for artifact_path in artifact_paths:
        if not artifact_path.is_file() or artifact_path.stat().st_size > max_bytes:
            continue
        text = _redacted_text(artifact_path.read_text(encoding="utf-8", errors="replace"))
        for component in component_payloads or [{"kind": "artifact", "name": artifact_path.stem}]:
            payload = {
                "mop_id": mop_id,
                "source_namespace": source_namespace,
                "artifact_type": _artifact_type(artifact_path),
                "artifact_path": artifact_path.relative_to(run_directory).as_posix(),
                "component": component,
                "text": text[:8000],
                "citation": f"{mop_id}:{artifact_path.name}:{component.get('kind')}/{component.get('name')}",
                "redaction_status": "redacted",
            }
            point_id = str(uuid5(NAMESPACE_URL, json.dumps(payload, sort_keys=True)))
            points.append(QdrantPointPayload(point_id=point_id, payload=payload))
    return points


def _citation_from_point(
    point: dict[str, Any],
    *,
    query: ComponentQuery,
    collection: str,
    min_score: float,
    exact_match_bonus: float,
) -> ReferenceCitation | None:
    payload = point.get("payload") or {}
    if not isinstance(payload, dict):
        return None
    component_payload = payload.get("component") or {}
    if not isinstance(component_payload, dict):
        return None
    matched_fields, score = _score_reference(
        query=query,
        payload=payload,
        component_payload=component_payload,
        exact_match_bonus=exact_match_bonus,
    )
    if score < min_score or not matched_fields:
        return None
    component = ComponentIdentity(
        kind=str(component_payload.get("kind") or query.component.kind),
        name=str(component_payload.get("name") or query.component.name),
        namespace=component_payload.get("namespace"),
        labels={
            str(key): str(value)
            for key, value in (component_payload.get("labels") or {}).items()
            if value is not None
        },
        helm_release_name=component_payload.get("helm_release_name"),
        helm_chart_name=component_payload.get("helm_chart_name"),
        helm_chart_version=component_payload.get("helm_chart_version"),
        image_repositories=[
            str(value) for value in component_payload.get("image_repositories") or []
        ],
    )
    excerpt = _redacted_text(str(payload.get("text") or payload.get("summary") or ""))[:1200]
    return ReferenceCitation(
        reference_id=str(point.get("id") or payload.get("citation") or query.query_id),
        qdrant_collection=collection,
        source_mop_id=payload.get("mop_id") or payload.get("source_mop_id"),
        source_artifact_type=payload.get("artifact_type"),
        source_namespace=payload.get("source_namespace"),
        component_identity=component,
        matched_fields=matched_fields,
        score=round(score, 4),
        confidence="high" if score >= 0.9 else "medium",
        excerpt=excerpt,
    )


def _score_reference(
    *,
    query: ComponentQuery,
    payload: dict[str, Any],
    component_payload: dict[str, Any],
    exact_match_bonus: float,
) -> tuple[list[str], float]:
    matched: list[str] = []
    score = 0.0
    query_component = query.component
    if component_payload.get("kind") == query_component.kind:
        matched.append("kind")
        score += 0.2
    if component_payload.get("name") == query_component.name:
        matched.append("name")
        score += exact_match_bonus
    if component_payload.get("helm_release_name") and (
        component_payload.get("helm_release_name") == query_component.helm_release_name
    ):
        matched.append("helm_release_name")
        score += 0.2
    if component_payload.get("helm_chart_name") and (
        component_payload.get("helm_chart_name") == query_component.helm_chart_name
    ):
        matched.append("helm_chart_name")
        score += 0.15
    payload_images = set(component_payload.get("image_repositories") or [])
    query_images = set(query_component.image_repositories)
    if payload_images and query_images and payload_images.intersection(query_images):
        matched.append("image_repositories")
        score += 0.15
    text = f"{payload.get('text') or ''} {payload.get('summary') or ''}".lower()
    exact_terms = [term.lower() for term in query.exact_terms if len(term) > 2]
    term_hits = sum(1 for term in exact_terms if term in text)
    if exact_terms and term_hits:
        matched.append("text_terms")
        score += min(0.1, term_hits / len(exact_terms) * 0.1)
    return matched, min(score, 1.0)


def _component_payloads(manifest: Any) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        return []
    payloads: list[dict[str, Any]] = []
    reconstruction = manifest.get("reconstruction") or {}
    for release in reconstruction.get("generated_values") or []:
        payloads.append(
            {
                "kind": "HelmRelease",
                "name": release.get("release_name"),
                "helm_release_name": release.get("release_name"),
                "helm_chart_name": release.get("chart_ref"),
            }
        )
    for item in reconstruction.get("generated_manifests") or []:
        payloads.append(
            {
                "kind": item.get("kind"),
                "name": item.get("name"),
                "namespace": item.get("namespace"),
            }
        )
    return [item for item in payloads if item.get("kind") and item.get("name")]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _artifact_type(path: Path) -> str:
    if path.name == "machine_execution_plan.yaml":
        return "machine_execution_plan"
    if path.suffix == ".md" and path.name.endswith(".installation.md"):
        return "installation_notes"
    if path.suffix == ".md":
        return "human_mop_markdown"
    return path.suffix.lstrip(".")


def _redacted_text(text: str) -> str:
    redacted = re.sub(
        r"(?i)(password|secret|token|credential|api[_-]?key)\s*[:=]\s*\S+",
        r"\1=***REDACTED***",
        text,
    )
    redacted = re.sub(
        r"(?i)(postgresql|mongodb|redis|clickhouse|kafka)://[^\s\"']+",
        r"\1://***REDACTED***",
        redacted,
    )
    return redacted
