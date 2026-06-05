from __future__ import annotations

from contextlib import AbstractContextManager
from time import perf_counter
from typing import Any
from uuid import uuid5, NAMESPACE_URL

from bosgenesis_mop_creation_agent.common.logging import get_logger
from bosgenesis_mop_creation_agent.config.settings import ObservabilitySettings, redact
from bosgenesis_mop_creation_agent.observability.models import AuditEvent, PhaseMetric

LOGGER = get_logger(__name__)
_OTEL_CONFIGURED = False


class ObservabilityService:
    """Create per-run redacted tracing/audit collectors.

    The implementation is intentionally dependency-light. If OpenTelemetry or
    Langfuse SDKs are unavailable, generation continues and the artifact records
    the disabled/unavailable sink status.
    """

    def __init__(self, settings: ObservabilitySettings) -> None:
        self._settings = settings
        self._otel_status = _configure_otel(settings)
        self._langfuse_client, self._langfuse_status = _configure_langfuse(settings)

    def trace_ids(self, run_id: str) -> dict[str, str | None]:
        return {
            "langfuse": (
                _stable_langfuse_trace_id(run_id, self._langfuse_client)
                if self._settings.langfuse_enabled
                else None
            ),
            "signoz": _stable_trace_id("signoz", run_id) if self._settings.signoz_enabled else None,
        }

    def start_run(
        self,
        *,
        mop_id: str,
        run_id: str,
        correlation_id: str,
        source_namespace: str,
        target_namespace: str,
        mode: str,
        caller: str,
    ) -> "ObservabilityRun":
        return ObservabilityRun(
            settings=self._settings,
            context={
                "mop_id": mop_id,
                "run_id": run_id,
                "correlation_id": correlation_id,
                "source_namespace": source_namespace,
                "target_namespace": target_namespace,
                "generation_mode": mode,
                "caller": caller,
            },
            trace_ids=self.trace_ids(run_id),
            sink_status={
                "structured_audit": "enabled" if self._settings.audit_enabled else "disabled",
                "phase_latency_metrics": (
                    "enabled" if self._settings.phase_metrics_enabled else "disabled"
                ),
                "warning_taxonomy": "enabled" if self._settings.warning_taxonomy_enabled else "disabled",
                "signoz": self._otel_status,
                "langfuse": self._langfuse_status,
            },
            langfuse_client=self._langfuse_client,
        )


class ObservabilityRun:
    def __init__(
        self,
        *,
        settings: ObservabilitySettings,
        context: dict[str, Any],
        trace_ids: dict[str, str | None],
        sink_status: dict[str, str],
        langfuse_client: Any | None = None,
    ) -> None:
        self._settings = settings
        self.context = context
        self.trace_ids = trace_ids
        self.audit_events: list[AuditEvent] = []
        self.phase_metrics: list[PhaseMetric] = []
        self._warning_taxonomy: dict[str, int] = {}
        self._sink_status = sink_status
        self._langfuse_client = langfuse_client
        self._service_details = redact(
            {
                "langfuse_endpoint": settings.langfuse_endpoint,
                "signoz_otlp_endpoint": settings.otlp_endpoint,
            }
        )

    def phase(self, phase: str, *, action: str | None = None) -> "_PhaseScope":
        return _PhaseScope(self, phase=phase, action=action or phase)

    def record_event(
        self,
        *,
        event_type: str,
        phase: str,
        action: str,
        status: str,
        severity: str = "info",
        latency_ms: float | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not self._settings.audit_enabled:
            return
        event = AuditEvent(
            event_type=event_type,
            phase=phase,
            action=action,
            status=status,
            severity=severity,
            latency_ms=latency_ms,
            message=message,
            details=redact(details or {}),
        )
        self.audit_events.append(event)
        LOGGER.info(
            "mop_audit_event",
            extra={**self.context, **event.to_dict()},
        )

    def record_warning(self, warning: str, *, phase: str = "warning_taxonomy") -> None:
        if not self._settings.warning_taxonomy_enabled:
            return
        category = classify_warning(warning)
        self._warning_taxonomy[category] = self._warning_taxonomy.get(category, 0) + 1
        self.record_event(
            event_type="warning_classified",
            phase=phase,
            action="classify_warning",
            status="warning",
            severity="warning",
            message=_safe_warning_message(warning),
            details={"warning_category": category},
        )

    def record_warnings(self, warnings: list[str], *, phase: str = "warning_taxonomy") -> None:
        for warning in warnings:
            self.record_warning(warning, phase=phase)

    def record_llm_reasoning(self, bounded_reasoning: Any, repair_suggestions: Any | None = None) -> None:
        details = {
            "bounded_reasoning": _reasoning_summary(bounded_reasoning),
            "repair_suggestions": _repair_summary(repair_suggestions),
            "prompt_payload_policy": "redacted_metadata_only_no_prompt_or_response_text",
        }
        attempted = _field_bool(bounded_reasoning, "attempted") or _field_bool(repair_suggestions, "attempted")
        self.record_event(
            event_type="langfuse_reasoning_trace",
            phase="llm_reasoning",
            action="record_reasoning_metadata",
            status="emitted" if self._sink_status.get("langfuse") == "enabled" else self._sink_status.get("langfuse", "disabled"),
            details=details | {"attempted": attempted},
        )
        self._emit_langfuse_reasoning(details | {"attempted": attempted})

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": "phase13.observability.v1",
            "trace_ids": self.trace_ids,
            "sinks": self._sink_status,
            "service_details": self._service_details,
            "context": redact(self.context),
            "phase_metrics": [metric.to_dict() for metric in self.phase_metrics],
            "phase_latency_ms": {
                metric.phase: round(metric.latency_ms, 3) for metric in self.phase_metrics
            },
            "warning_taxonomy": dict(sorted(self._warning_taxonomy.items())),
            "audit_events": [event.to_dict() for event in self.audit_events],
            "audit_event_count": len(self.audit_events),
            "redaction_status": "metadata_only_no_secret_payload",
        }

    def _record_phase_complete(self, phase: str, status: str, latency_ms: float) -> None:
        if self._settings.phase_metrics_enabled:
            self.phase_metrics.append(PhaseMetric(phase=phase, status=status, latency_ms=latency_ms))
        self.record_event(
            event_type="phase_completed",
            phase=phase,
            action=phase,
            status=status,
            severity="error" if status == "failed" else "info",
            latency_ms=latency_ms,
        )

    def _emit_langfuse_reasoning(self, details: dict[str, Any]) -> None:
        if self._sink_status.get("langfuse") != "enabled" or self._langfuse_client is None:
            return
        try:
            metadata = redact({**self.context, **details})
            if hasattr(self._langfuse_client, "trace"):
                self._emit_langfuse_v2_event(metadata, details)
            elif hasattr(self._langfuse_client, "create_event"):
                self._emit_langfuse_v3_event(metadata, details)
            else:
                raise AttributeError("Langfuse client has no supported trace/event API")
            if hasattr(self._langfuse_client, "flush"):
                self._langfuse_client.flush()
        except Exception as exc:  # pragma: no cover - telemetry must not break generation.
            self._sink_status["langfuse"] = "enabled_export_failed"
            self.record_event(
                event_type="telemetry_export_failed",
                phase="llm_reasoning",
                action="emit_langfuse_reasoning_trace",
                status="failed",
                severity="warning",
                message=str(exc),
            )

    def _emit_langfuse_v2_event(self, metadata: dict[str, Any], details: dict[str, Any]) -> None:
        trace = self._langfuse_client.trace(
            id=self.trace_ids.get("langfuse"),
            name="bosgenesis_mop_creation_reasoning",
            user_id=str(self.context.get("caller") or "unknown"),
            session_id=str(self.context.get("correlation_id") or self.context.get("run_id")),
            metadata=metadata,
            tags=["bosgenesis", "mop-creation-agent", "phase13"],
        )
        if hasattr(trace, "event"):
            trace.event(
                name="llm_reasoning_metadata",
                metadata=redact(details),
                level="DEFAULT",
            )

    def _emit_langfuse_v3_event(self, metadata: dict[str, Any], details: dict[str, Any]) -> None:
        self._langfuse_client.create_event(
            trace_context={"trace_id": self.trace_ids.get("langfuse")},
            name="llm_reasoning_metadata",
            input={"policy": "redacted_metadata_only_no_prompt_or_response_text"},
            output={
                "bounded_reasoning_status": details.get("bounded_reasoning", {}).get("status"),
                "repair_suggestions_status": details.get("repair_suggestions", {}).get("status"),
                "attempted": details.get("attempted"),
            },
            metadata=metadata,
            level="DEFAULT",
        )


class _PhaseScope(AbstractContextManager["_PhaseScope"]):
    def __init__(self, run: ObservabilityRun, *, phase: str, action: str) -> None:
        self._run = run
        self._phase = phase
        self._action = action
        self._started = 0.0
        self._span = None

    def __enter__(self) -> "_PhaseScope":
        self._started = perf_counter()
        self._run.record_event(
            event_type="phase_started",
            phase=self._phase,
            action=self._action,
            status="started",
        )
        self._span = _start_otel_span(self._phase, self._run.context)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        latency_ms = (perf_counter() - self._started) * 1000
        status = "failed" if exc is not None else "ok"
        if self._span is not None:
            try:
                if exc is not None and hasattr(self._span, "record_exception"):
                    self._span.record_exception(exc)
                self._span.__exit__(exc_type, exc, traceback)
            except Exception:  # pragma: no cover - telemetry must not break generation.
                LOGGER.warning("otel_span_close_failed", extra=self._run.context)
        self._run._record_phase_complete(self._phase, status, latency_ms)
        return False


def classify_warning(warning: str) -> str:
    lowered = warning.lower()
    if "qdrant" in lowered:
        return "qdrant"
    if "mcp" in lowered or "helm manager" in lowered or "k8s" in lowered:
        return "mcp"
    if "postgres" in lowered or "clickhouse" in lowered or "snapshot" in lowered:
        return "snapshot"
    if "llm" in lowered or "reasoning" in lowered:
        return "llm"
    if "memory" in lowered or "redis" in lowered or "pgvector" in lowered:
        return "memory"
    if "secret" in lowered or "blocked" in lowered or "excluded" in lowered:
        return "safety"
    if "manifest" in lowered or "reconstruction" in lowered or "helm_release" in lowered:
        return "reconstruction"
    if "validation" in lowered or "validate" in lowered:
        return "validation"
    return "general"


def _configure_otel(settings: ObservabilitySettings) -> str:
    global _OTEL_CONFIGURED
    if not settings.signoz_enabled:
        return "disabled"
    if not settings.otlp_endpoint:
        return "enabled_endpoint_missing"
    if _OTEL_CONFIGURED:
        return "enabled"
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return "enabled_sdk_unavailable"
    try:
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": "bosgenesis-mop-creation-agent",
                    "service.namespace": "bosgenesis",
                    "deployment.environment": "bosgenesis-lab",
                }
            )
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=settings.otlp_endpoint,
                    insecure=settings.otlp_endpoint.startswith("http://"),
                )
            )
        )
        trace.set_tracer_provider(provider)
        _OTEL_CONFIGURED = True
    except Exception as exc:  # pragma: no cover - telemetry must not break generation.
        LOGGER.warning("otel_config_failed", extra={"error": str(exc)})
        return "enabled_config_failed"
    return "enabled"


def _configure_langfuse(settings: ObservabilitySettings) -> tuple[Any | None, str]:
    if not settings.langfuse_enabled:
        return None, "disabled"
    if not settings.langfuse_endpoint:
        return None, "enabled_endpoint_missing"
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None, "enabled_credentials_missing"
    try:
        from langfuse import Langfuse
    except ImportError:
        return None, "enabled_sdk_unavailable"
    try:
        return (
            Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_endpoint,
            ),
            "enabled",
        )
    except Exception as exc:  # pragma: no cover - telemetry must not break generation.
        LOGGER.warning("langfuse_config_failed", extra={"error": str(exc)})
        return None, "enabled_config_failed"


def _start_otel_span(phase: str, context: dict[str, Any]) -> Any | None:
    try:
        from opentelemetry import trace
    except ImportError:
        return None
    tracer = trace.get_tracer("bosgenesis.mop_creation_agent")
    span = tracer.start_as_current_span(f"mop_creation.{phase}")
    manager = span.__enter__()
    for key, value in context.items():
        if value is not None and hasattr(manager, "set_attribute"):
            manager.set_attribute(f"mop.{key}", str(value))
    return span


def _stable_trace_id(prefix: str, run_id: str) -> str:
    return f"{prefix}-{uuid5(NAMESPACE_URL, f'bosgenesis-mop:{prefix}:{run_id}').hex}"


def _stable_langfuse_trace_id(run_id: str, client: Any | None) -> str:
    if client is not None and hasattr(client, "create_trace_id"):
        return str(client.create_trace_id(seed=run_id))
    try:
        from langfuse import Langfuse

        if hasattr(Langfuse, "create_trace_id"):
            return str(Langfuse.create_trace_id(seed=run_id))
    except ImportError:
        pass
    return uuid5(NAMESPACE_URL, f"bosgenesis-mop:langfuse:{run_id}").hex


def _safe_warning_message(warning: str) -> str:
    return str(redact(warning))[:240]


def _reasoning_summary(result: Any) -> dict[str, Any]:
    if result is None:
        return {"enabled": False, "attempted": False, "status": "missing"}
    diagnostics = _field(result, "diagnostics")
    return {
        "enabled": _field_bool(result, "enabled"),
        "attempted": _field_bool(result, "attempted"),
        "status": _field(result, "status", "unknown"),
        "finding_count": len(_field(result, "findings", []) or []),
        "diagnostics": _diagnostics_dict(diagnostics),
    }


def _repair_summary(result: Any) -> dict[str, Any]:
    if result is None:
        return {"enabled": False, "attempted": False, "status": "missing"}
    diagnostics = _field(result, "diagnostics")
    return {
        "enabled": _field_bool(result, "enabled"),
        "attempted": _field_bool(result, "attempted"),
        "status": _field(result, "status", "unknown"),
        "suggestion_count": len(_field(result, "suggestions", []) or []),
        "diagnostics": _diagnostics_dict(diagnostics),
    }


def _field(result: Any, name: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def _field_bool(result: Any, name: str) -> bool:
    return bool(_field(result, name, False))


def _diagnostics_dict(diagnostics: Any) -> dict[str, Any]:
    if isinstance(diagnostics, dict):
        return redact(diagnostics)
    if hasattr(diagnostics, "model_dump"):
        return redact(diagnostics.model_dump(mode="json"))
    return {}
