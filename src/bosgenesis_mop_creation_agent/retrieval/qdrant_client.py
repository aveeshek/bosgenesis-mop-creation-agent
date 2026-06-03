from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib import error, request

from bosgenesis_mop_creation_agent.config.settings import QdrantRetrievalSettings
from bosgenesis_mop_creation_agent.retrieval.models import ComponentQuery, QdrantPointPayload


class QdrantClientError(RuntimeError):
    pass


class QdrantReadOnlyClient:
    def __init__(self, settings: QdrantRetrievalSettings) -> None:
        self._settings = settings

    def search_component(self, query: ComponentQuery) -> list[dict[str, Any]]:
        if not self._settings.endpoint:
            raise QdrantClientError("qdrant_endpoint_missing")
        endpoint = self._settings.endpoint.rstrip("/")
        url = f"{endpoint}/collections/{self._settings.collection}/points/scroll"
        body = {
            "limit": max(self._settings.top_k * 4, self._settings.top_k),
            "with_payload": True,
            "with_vector": False,
            "filter": _filter_for_query(query),
        }
        payload = self._post_json(url, body)
        result = payload.get("result") or {}
        points = result.get("points") or []
        return [point for point in points if isinstance(point, dict)]

    def upsert_points(self, points: list[QdrantPointPayload]) -> dict[str, Any]:
        if not self._settings.endpoint:
            raise QdrantClientError("qdrant_endpoint_missing")
        self.ensure_collection()
        endpoint = self._settings.endpoint.rstrip("/")
        url = f"{endpoint}/collections/{self._settings.collection}/points?wait=true"
        body = {
            "points": [
                {
                    "id": point.point_id,
                    "vector": _hash_vector(
                        json.dumps(point.payload, sort_keys=True),
                        self._settings.ingestion_vector_size,
                    ),
                    "payload": point.payload,
                }
                for point in points
            ]
        }
        return self._put_json(url, body)

    def ensure_collection(self) -> dict[str, Any]:
        if not self._settings.endpoint:
            raise QdrantClientError("qdrant_endpoint_missing")
        endpoint = self._settings.endpoint.rstrip("/")
        collection_url = f"{endpoint}/collections/{self._settings.collection}"
        try:
            return self._get_json(collection_url)
        except QdrantClientError as exc:
            if "HTTP Error 404" not in str(exc):
                raise
        body = {
            "vectors": {
                "size": self._settings.ingestion_vector_size,
                "distance": "Cosine",
            }
        }
        return self._put_json(collection_url, body)

    def _post_json(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._send_json("POST", url, body)

    def _put_json(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._send_json("PUT", url, body)

    def _get_json(self, url: str) -> dict[str, Any]:
        return self._send_json("GET", url, None)

    def _send_json(self, method: str, url: str, body: dict[str, Any] | None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self._settings.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise QdrantClientError(str(exc)) from exc


def _filter_for_query(query: ComponentQuery) -> dict[str, Any]:
    should = []
    component = query.component
    field_values = {
        "component.kind": component.kind,
        "component.name": component.name,
        "component.helm_release_name": component.helm_release_name,
        "component.helm_chart_name": component.helm_chart_name,
    }
    for key, value in field_values.items():
        if value:
            should.append({"key": key, "match": {"value": value}})
    for image in component.image_repositories[:3]:
        should.append({"key": "component.image_repositories", "match": {"value": image}})
    if not should:
        should.append({"key": "component.name", "match": {"value": component.name}})
    return {"should": should}


def _hash_vector(text: str, size: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for index in range(size):
        byte = digest[index % len(digest)]
        values.append((byte / 127.5) - 1.0)
    return values
