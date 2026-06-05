import json
from pathlib import Path

from bosgenesis_mop_creation_agent.config.settings import AgentSettings, Settings
from bosgenesis_mop_creation_agent.core.orchestrator import MoPCreationOrchestrator
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest


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
