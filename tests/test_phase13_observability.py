import json
from pathlib import Path

from bosgenesis_mop_creation_agent.config.settings import ObservabilitySettings
from bosgenesis_mop_creation_agent.config.settings import AgentSettings, Settings
from bosgenesis_mop_creation_agent.core.orchestrator import MoPCreationOrchestrator
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest
from bosgenesis_mop_creation_agent.observability.service import ObservabilityService


def test_phase13_manifest_records_audit_spans_metrics_and_warning_taxonomy(tmp_path: Path) -> None:
    orchestrator = MoPCreationOrchestrator(
        Settings(agent=AgentSettings(local_storage_path=str(tmp_path)))
    )

    response = orchestrator.generate(
        MoPGenerationRequest(
            target_namespace="bosgenesis-copy-dev",
            caller="pytest",
            correlation_id="phase13-correlation",
        )
    )

    manifest = json.loads(Path(response.artifacts.artifact_manifest_path).read_text())
    observability = manifest["observability"]

    assert observability["schema_version"] == "phase13.observability.v1"
    assert len(observability["trace_ids"]["langfuse"]) == 32
    assert observability["trace_ids"]["signoz"].startswith("signoz-")
    assert observability["sinks"]["structured_audit"] == "enabled"
    assert observability["sinks"]["phase_latency_metrics"] == "enabled"
    assert "langfuse_endpoint" in observability["service_details"]
    assert "signoz_otlp_endpoint" in observability["service_details"]
    assert observability["redaction_status"] == "metadata_only_no_secret_payload"

    phase_names = {item["phase"] for item in observability["phase_metrics"]}
    assert {
        "memory_read",
        "read_latest_snapshot",
        "enrich_from_mcp",
        "classify_resources",
        "qdrant_reference_lookup",
        "render_artifacts",
        "memory_write",
    }.issubset(phase_names)
    assert all(item["latency_ms"] >= 0 for item in observability["phase_metrics"])

    event_types = {item["event_type"] for item in observability["audit_events"]}
    assert {
        "request_received",
        "mcp_enrichment",
        "qdrant_lookup",
        "rendering",
        "validation",
        "memory_read",
        "memory_write",
        "response_ready",
    }.issubset(event_types)

    validation_events = [
        item for item in observability["audit_events"] if item["event_type"] == "validation"
    ]
    assert validation_events
    assert validation_events[0]["details"]["policy"] == (
        "every_generated_step_requires_evidence_refs_or_inference_label"
    )
    assert validation_events[0]["details"]["missing_evidence_or_inference_count"] == 0

    assert observability["warning_taxonomy"]
    assert "snapshot" in observability["warning_taxonomy"]
    assert "mcp" in observability["warning_taxonomy"]
    assert observability["audit_event_count"] == len(observability["audit_events"])


class _FakeLangfuseV3Client:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.flushed = False

    def create_trace_id(self, *, seed: str) -> str:
        return f"{seed.replace('-', '')[:32]:0<32}"[:32]

    def create_event(self, **kwargs: object) -> None:
        self.events.append(kwargs)

    def flush(self) -> None:
        self.flushed = True


class _FailingLangfuseClient(_FakeLangfuseV3Client):
    def create_event(self, **kwargs: object) -> None:
        raise RuntimeError("langfuse unavailable")


def test_langfuse_v3_event_export_uses_redacted_metadata_only() -> None:
    service = ObservabilityService(
        ObservabilitySettings(
            langfuse_enabled=True,
            langfuse_endpoint="http://langfuse-web.bosgenesis.svc.cluster.local:3000",
            langfuse_public_key="public",
            langfuse_secret_key="secret",
            signoz_enabled=False,
        )
    )
    fake_client = _FakeLangfuseV3Client()
    run = service.start_run(
        mop_id="mop-1",
        run_id="12345678-1234-5678-1234-567812345678",
        correlation_id="corr-1",
        source_namespace="bosgenesis",
        target_namespace="bosgenesis-copy",
        mode="platform-only",
        caller="pytest",
    )
    run._langfuse_client = fake_client
    run._sink_status["langfuse"] = "enabled"
    run.trace_ids["langfuse"] = fake_client.create_trace_id(seed=run.context["run_id"])

    run.record_llm_reasoning(
        {
            "enabled": True,
            "attempted": True,
            "status": "generated",
            "findings": [{"label": "requires_human_review"}],
            "diagnostics": {"prompt_chars": 42, "secret_key": "must-redact"},
        },
        {
            "enabled": True,
            "attempted": True,
            "status": "generated",
            "suggestions": [{"label": "manual_review"}],
            "diagnostics": {"response_chars": 24},
        },
    )

    assert fake_client.flushed is True
    assert fake_client.events
    event = fake_client.events[0]
    assert event["name"] == "llm_reasoning_metadata"
    assert event["trace_context"] == {"trace_id": run.trace_ids["langfuse"]}
    assert event["input"] == {"policy": "redacted_metadata_only_no_prompt_or_response_text"}
    assert "raw prompt" not in json.dumps(event).lower()
    assert "***REDACTED***" in json.dumps(event)
    assert run.summary()["sinks"]["langfuse"] == "enabled"


def test_langfuse_export_failure_is_audited_without_failing_generation() -> None:
    service = ObservabilityService(
        ObservabilitySettings(
            langfuse_enabled=True,
            langfuse_endpoint="http://langfuse-web.bosgenesis.svc.cluster.local:3000",
            langfuse_public_key="public",
            langfuse_secret_key="secret",
            signoz_enabled=False,
        )
    )
    run = service.start_run(
        mop_id="mop-1",
        run_id="12345678-1234-5678-1234-567812345678",
        correlation_id="corr-1",
        source_namespace="bosgenesis",
        target_namespace="bosgenesis-copy",
        mode="platform-only",
        caller="pytest",
    )
    run._langfuse_client = _FailingLangfuseClient()
    run._sink_status["langfuse"] = "enabled"

    run.record_llm_reasoning({"enabled": True, "attempted": True, "status": "generated"})

    summary = run.summary()
    assert summary["sinks"]["langfuse"] == "enabled_export_failed"
    assert any(
        event["event_type"] == "telemetry_export_failed"
        for event in summary["audit_events"]
    )
