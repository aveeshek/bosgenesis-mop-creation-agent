from __future__ import annotations

import os
from typing import Protocol

from bosgenesis_mop_creation_agent.config.settings import LlmModelProfile, LlmSettings


class ChatModel(Protocol):
    def invoke(self, prompt: str): ...


def build_azure_chat_model(settings: LlmSettings) -> ChatModel:
    return build_chat_model(settings)


def build_chat_model(settings: LlmSettings) -> ChatModel:
    profile = settings.active_profile()
    if not profile.enabled:
        raise RuntimeError(f"LLM model profile '{settings.default_model}' is disabled.")
    if profile.provider == "azure_openai":
        return _build_azure_chat_model(settings, profile)
    if profile.provider == "ollama":
        return _build_ollama_chat_model(settings, profile)
    raise RuntimeError(f"Unsupported LLM provider '{profile.provider}' for '{settings.default_model}'.")


def _build_azure_chat_model(settings: LlmSettings, profile: LlmModelProfile) -> ChatModel:
    try:
        from azure.identity import AzureCliCredential, get_bearer_token_provider
        from langchain_openai import AzureChatOpenAI
    except ImportError as exc:  # pragma: no cover - depends on optional runtime install
        raise RuntimeError(
            "Azure OpenAI repair suggestions require azure-identity and langchain-openai."
        ) from exc

    endpoint = profile.azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = profile.azure_deployment or os.getenv("OPENAI_DEPLOYMENT")
    api_version = profile.azure_api_version or os.getenv("OPENAI_API_VERSION")
    if not endpoint or not deployment or not api_version:
        raise RuntimeError(
            "Azure OpenAI repair suggestions require AZURE_OPENAI_ENDPOINT, "
            "OPENAI_DEPLOYMENT, and OPENAI_API_VERSION."
        )

    credential = AzureCliCredential()
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureChatOpenAI(
        azure_ad_token_provider=token_provider,
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        openai_api_version=api_version,
        temperature=profile.temperature
        if profile.temperature is not None
        else settings.temperature,
        max_tokens=profile.max_tokens if profile.max_tokens is not None else settings.max_tokens,
    )


def _build_ollama_chat_model(settings: LlmSettings, profile: LlmModelProfile) -> ChatModel:
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:  # pragma: no cover - depends on optional runtime install
        raise RuntimeError("Ollama repair suggestions require langchain-ollama.") from exc

    model = profile.model or settings.default_model
    base_url = profile.base_url or os.getenv("OLLAMA_BASE_URL")
    if not model or not base_url:
        raise RuntimeError("Ollama repair suggestions require model and base_url.")

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=profile.temperature
        if profile.temperature is not None
        else settings.temperature,
        num_predict=profile.max_tokens if profile.max_tokens is not None else settings.max_tokens,
    )
