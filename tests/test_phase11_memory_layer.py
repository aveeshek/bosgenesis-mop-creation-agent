import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from bosgenesis_mop_creation_agent.api.app import create_app
from bosgenesis_mop_creation_agent.config.settings import AgentSettings, MemorySettings, Settings
from bosgenesis_mop_creation_agent.config.settings import MemoryBackendSettings
from bosgenesis_mop_creation_agent.memory.adapters import PgVectorMemoryAdapter, RedisMemoryAdapter
from bosgenesis_mop_creation_agent.memory.models import MemoryRecord
from bosgenesis_mop_creation_agent.memory.service import AgentMemoryService


def _wait_for_generated(client: TestClient, mop_id: str) -> dict:
    deadline = time.monotonic() + 10
    payload = {}
    while time.monotonic() < deadline:
        response = client.get(f"/mop-creation/{mop_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] != "accepted":
            return payload
        time.sleep(0.05)
    raise AssertionError(f"MoP generation did not complete in time: {payload}")


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, list[str]] = {}

    def lrange(self, name: str, start: int, end: int) -> list[str]:
        values = self.values.get(name, [])
        if start < 0:
            start = max(len(values) + start, 0)
        if end < 0:
            end = len(values) + end
        return values[start : end + 1]

    def rpush(self, name: str, *values: str) -> int:
        self.values.setdefault(name, []).extend(values)
        return len(self.values[name])

    def ltrim(self, name: str, start: int, end: int) -> bool:
        values = self.values.get(name, [])
        if start < 0:
            start = max(len(values) + start, 0)
        if end < 0:
            end = len(values) + end
        self.values[name] = values[start : end + 1]
        return True


def test_phase11_default_backend_mapping() -> None:
    settings = MemorySettings()

    assert settings.langmem_enabled is True
    assert settings.redis.enabled is True
    assert settings.redis.db == 0
    assert settings.redis.key_prefix == "mop-agent-memory"
    assert settings.pgvector.enabled is True
    assert settings.qdrant.enabled is False
    assert settings.letta.enabled is False
    assert settings.qdrant.collection == "mop_agent_memory"


def test_phase11_redis_adapter_round_trips_namespace_records() -> None:
    fake_redis = _FakeRedis()
    adapter = RedisMemoryAdapter(MemorySettings().redis, client=fake_redis)
    records = [
        MemoryRecord(
            memory_id="mem-1",
            namespace_key="namespace:bosgenesis",
            kind="short_term",
            summary="safe summary one",
        ),
        MemoryRecord(
            memory_id="mem-2",
            namespace_key="namespace:bosgenesis",
            kind="episodic",
            summary="safe summary two",
        ),
    ]

    write_status, write_warnings = adapter.write(records)
    read_records, read_status, read_warnings = adapter.read("namespace:bosgenesis", limit=5)

    assert write_status == "ok"
    assert write_warnings == []
    assert read_status == "ok"
    assert read_warnings == []
    assert [record.memory_id for record in read_records] == ["mem-1"]
    assert "mop-agent-memory:namespace:bosgenesis:records" in fake_redis.values


def test_phase11_pgvector_adapter_requires_dsn_and_filters_to_episodic() -> None:
    adapter = PgVectorMemoryAdapter(MemoryBackendSettings(enabled=True, table="mop_agent_memory"))
    records = [
        MemoryRecord(
            memory_id="mem-short",
            namespace_key="namespace:bosgenesis",
            kind="short_term",
            summary="safe short summary",
        ),
        MemoryRecord(
            memory_id="mem-episodic",
            namespace_key="namespace:bosgenesis",
            kind="episodic",
            summary="safe episodic summary",
        ),
    ]

    status, warnings = adapter.write(records)

    assert status == "unavailable"
    assert warnings == ["pgvector_memory_unavailable:memory_pgvector_dsn_missing"]


def test_phase11_memory_can_be_disabled(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            Settings(
                agent=AgentSettings(local_storage_path=str(tmp_path)),
                memory=MemorySettings(enabled=False),
            )
        )
    )

    accepted = client.post(
        "/mop-creation/generate",
        json={"target_namespace": "memory-disabled", "caller": "pytest"},
    ).json()
    generated = _wait_for_generated(client, accepted["mop_id"])

    assert generated["memory_status"] == "disabled"
    assert generated["memory_read_count"] == 0
    assert generated["memory_written_count"] == 0

    manifest = json.loads(
        Path(generated["artifacts"]["artifact_manifest_path"]).read_text(encoding="utf-8")
    )
    assert manifest["memory"]["enabled"] is False


def test_phase11_memory_stores_only_non_secret_summaries() -> None:
    service = AgentMemoryService(MemorySettings(enabled=True, max_summary_chars=200))

    result = service.write_generation_summary(
        namespace_key="namespace:bosgenesis",
        mop_id="mop-1",
        run_id="run-1",
        correlation_id="corr-1",
        target_namespace="mirror",
        inventory=None,
        classification=None,
        qdrant_references=None,
        warnings=["password: should-not-be-stored"],
    )
    context = service.read_context(
        namespace_key="namespace:bosgenesis",
        correlation_id="corr-2",
        run_id="run-2",
    )

    assert result.status == "ok"
    assert result.written_count == 3
    assert context.read_count == 3
    summaries = " ".join(record.summary for record in context.records)
    assert "password" not in summaries.lower()
    assert "should-not-be-stored" not in summaries
    assert all(record.redaction_status == "non_secret_summary_only" for record in context.records)


def test_phase11_later_runs_use_prior_safe_memory_context(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            Settings(
                agent=AgentSettings(local_storage_path=str(tmp_path)),
                memory=MemorySettings(enabled=True),
            )
        )
    )

    first = client.post(
        "/mop-creation/generate",
        json={"target_namespace": "memory-first", "caller": "pytest"},
    ).json()
    first_generated = _wait_for_generated(client, first["mop_id"])

    second = client.post(
        "/mop-creation/generate",
        json={"target_namespace": "memory-second", "caller": "pytest"},
    ).json()
    second_generated = _wait_for_generated(client, second["mop_id"])

    assert first_generated["memory_status"] == "ok"
    assert first_generated["memory_read_count"] == 0
    assert first_generated["memory_written_count"] == 3
    assert second_generated["memory_status"] == "ok"
    assert second_generated["memory_read_count"] == 3
    assert second_generated["memory_written_count"] == 3

    notes = Path(second_generated["artifacts"]["installation_notes_path"]).read_text(
        encoding="utf-8"
    )
    manifest = json.loads(
        Path(second_generated["artifacts"]["artifact_manifest_path"]).read_text(encoding="utf-8")
    )

    assert "memory_context:" in notes
    assert "prior_context_only_not_current_fact" in notes
    assert manifest["memory"]["enabled"] is True
    assert manifest["memory"]["read_count"] == 3
    assert manifest["memory"]["write_status"] == "ok"
    assert manifest["memory"]["written_count"] == 3
