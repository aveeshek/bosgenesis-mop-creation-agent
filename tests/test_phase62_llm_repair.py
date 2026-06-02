from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.config.settings import LlmSettings
from bosgenesis_mop_creation_agent.llm.model_gateway import build_chat_model
from bosgenesis_mop_creation_agent.llm.repair_suggester import build_repair_suggestions
from bosgenesis_mop_creation_agent.reconstruction.models import ReconstructionPlan
from bosgenesis_mop_creation_agent.sources.snapshot_models import InventoryResource, NormalizedInventory


class _FakeChatModel:
    def __init__(self, content: str, *, additional_kwargs: dict | None = None) -> None:
        self.content = content
        self.additional_kwargs = additional_kwargs or {}
        self.prompt = ""

    def invoke(self, prompt: str):
        self.prompt = prompt
        return type(
            "Response",
            (),
            {"content": self.content, "additional_kwargs": self.additional_kwargs},
        )()


def test_phase62_llm_repair_is_disabled_by_default() -> None:
    result = build_repair_suggestions(
        settings=LlmSettings(),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
    )

    assert result.enabled is False
    assert result.status == "disabled"
    assert result.suggestions == []


def test_phase62_llm_profiles_support_four_configured_models() -> None:
    settings = LlmSettings()

    assert settings.default_model == "gemma4:26b"
    assert settings.active_profile().provider == "ollama"
    assert settings.active_profile().model == "gemma4:26b"
    assert set(settings.model_profiles) >= {
        "gemma4:26b",
        "gpt-4.1-mini",
        "gpt-5",
        "gemma4",
        "llama70b",
    }

    default_gemma = LlmSettings(default_model="gemma4:26b").active_profile()
    gemma = LlmSettings(default_model="gemma4").active_profile()
    llama = LlmSettings(default_model="llama70b").active_profile()
    azure = LlmSettings(default_model="gpt-4.1-mini").active_profile()

    assert default_gemma.provider == "ollama"
    assert default_gemma.model == "gemma4:26b"
    assert default_gemma.base_url == "http://ollama.bosgenesis.svc.cluster.local:11434"
    assert gemma.provider == "ollama"
    assert gemma.model == "gemma4:26b"
    assert gemma.base_url == "http://ollama.bosgenesis.svc.cluster.local:11434"
    assert llama.provider == "ollama"
    assert llama.model == "llama3.3:70b"
    assert llama.base_url == "http://ollama-llama70b.bosgenesis.svc.cluster.local:11434"
    assert azure.provider == "azure_openai"
    assert azure.azure_deployment == "bos-trainium-sigma-gpt-4.1-mini"


def test_phase62_llm_gateway_rejects_unknown_provider() -> None:
    settings = LlmSettings(default_model="unsupported-provider")
    settings.provider = "not-a-provider"

    try:
        build_chat_model(settings)
    except RuntimeError as exc:
        assert "Unsupported LLM provider" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected unsupported provider failure")


def test_phase62_llm_repair_returns_labeled_suggestions_only() -> None:
    model = _FakeChatModel(
        """
        {
          "suggestions": [
            {
              "target_type": "raw_manifest",
              "target_name": "Deployment/api",
              "issue": "source_spec_missing",
              "suggestion": "Ask the owner to confirm replicas, selector labels, and container image.",
              "confidence": 0.91,
              "rationale": "The issue is known but executable fields need human confirmation.",
              "evidence_refs": ["snapshot:test"]
            },
            {
              "target_type": "raw_manifest",
              "target_name": "Service/api",
              "issue": "ports_missing",
              "suggestion": "Infer port 80.",
              "confidence": 0.40,
              "rationale": "Weak evidence.",
              "evidence_refs": []
            }
          ]
        }
        """
    )

    result = build_repair_suggestions(
        settings=LlmSettings(repair_suggestions_enabled=True, minimum_confidence=0.85),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
        chat_model=model,
    )

    assert result.enabled is True
    assert result.attempted is True
    assert result.status == "generated"
    assert len(result.suggestions) == 1
    suggestion = result.suggestions[0]
    assert suggestion.label == "llm_suggestion_requires_human_review"
    assert suggestion.executable_yaml_allowed is False
    assert "Do not output executable YAML" in model.prompt
    assert "JSON schema" in model.prompt
    assert result.diagnostics.parse_status == "valid_json"
    assert result.diagnostics.response_source == "content"
    assert result.diagnostics.accepted_count == 1
    assert result.diagnostics.rejected_low_confidence_count == 1


def test_phase62_llm_repair_reports_invalid_structured_output() -> None:
    model = _FakeChatModel("I think you should review the deployment manually.")

    result = build_repair_suggestions(
        settings=LlmSettings(repair_suggestions_enabled=True, minimum_confidence=0.85),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
        chat_model=model,
    )

    assert result.status == "invalid_structured_output"
    assert result.suggestions == []
    assert result.diagnostics.parse_status == "invalid_no_json_object"
    assert result.warnings == ["llm_repair_suggestions_invalid_structured_output"]


def test_phase62_llm_repair_reports_schema_rejections() -> None:
    model = _FakeChatModel(
        """
        {
          "suggestions": [
            {
              "target_type": "raw_manifest",
              "target_name": "Deployment/api",
              "issue": "source_spec_missing",
              "suggestion": "Ask the owner to confirm container image.",
              "confidence": 1.2,
              "rationale": "Invalid confidence value.",
              "evidence_refs": ["snapshot:test"]
            }
          ]
        }
        """
    )

    result = build_repair_suggestions(
        settings=LlmSettings(repair_suggestions_enabled=True, minimum_confidence=0.85),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
        chat_model=model,
    )

    assert result.status == "invalid_structured_output"
    assert result.diagnostics.parse_status == "invalid_schema"
    assert result.diagnostics.rejected_invalid_count == 1


def test_phase62_llm_repair_uses_fallback_metadata_without_storing_raw_output() -> None:
    model = _FakeChatModel(
        "",
        additional_kwargs={
            "message": {
                "thinking": """
                {
                  "suggestions": [
                    {
                      "target_type": "raw_manifest",
                      "target_name": "Deployment/api",
                      "issue": "source_spec_missing",
                      "suggestion": "Ask the owner to confirm container image before execution.",
                      "confidence": 0.92,
                      "rationale": "The gap is known but executable YAML requires human confirmation.",
                      "evidence_refs": ["snapshot:test"]
                    }
                  ]
                }
                """
            }
        },
    )

    result = build_repair_suggestions(
        settings=LlmSettings(repair_suggestions_enabled=True, minimum_confidence=0.85),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
        chat_model=model,
    )

    assert result.status == "generated"
    assert len(result.suggestions) == 1
    assert result.diagnostics.response_source == "additional_kwargs"
    assert result.diagnostics.response_chars > 0
    assert not hasattr(result.diagnostics, "raw_response")


def test_phase62_llm_prompt_uses_redacted_issue_context_not_manifest_values() -> None:
    model = _FakeChatModel('{"suggestions": []}')
    inventory = NormalizedInventory(
        source="test",
        namespace="bosgenesis",
        snapshot_id="snapshot",
        resources=[
            InventoryResource(kind="Event", name="api-event", namespace="bosgenesis", source="test")
        ],
    )

    build_repair_suggestions(
        settings=LlmSettings(repair_suggestions_enabled=True),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=classify_inventory(inventory),
        correlation_id="test",
        chat_model=model,
    )

    assert "source_spec_missing" in model.prompt
    assert "clear-text" not in model.prompt.lower()
    assert "clear-token" not in model.prompt.lower()
