from __future__ import annotations

from copy import deepcopy
from typing import Any

import yaml

from bosgenesis_mop_creation_agent.sources.snapshot_models import InventoryHelmRelease


SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "auth",
    "credential",
    "passwd",
    "password",
    "privatekey",
    "secret",
    "token",
)

REDACTED = "<REDACTED_PROVIDE_APPROVED_VALUE>"


def extract_values(release: InventoryHelmRelease) -> dict[str, Any]:
    payloads = [release.normalized_payload]
    mcp_live = release.normalized_payload.get("mcp_live")
    if isinstance(mcp_live, dict):
        payloads.insert(0, mcp_live)
    for payload in payloads:
        value = payload.get("values") if isinstance(payload, dict) else None
        extracted = _unwrap_values(value)
        if extracted is not None:
            return extracted
    return {}


def redacted_values_yaml(release: InventoryHelmRelease) -> str:
    values = extract_values(release)
    redacted = _redact(deepcopy(values))
    if not redacted:
        redacted = {
            "_note": (
                "No Helm values were available from evidence. Review chart defaults "
                "and provide required overrides before install."
            )
        }
    return yaml.safe_dump(redacted, sort_keys=False, explicit_start=True)


def _unwrap_values(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        for key in ("values", "user_values", "computed_values", "data", "result"):
            nested = value.get(key)
            if isinstance(nested, dict):
                return nested
        return value
    return None


def _redact(value: Any, key_hint: str = "") -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                result[key] = REDACTED
            else:
                result[key] = _redact(item, key_text)
        return result
    if isinstance(value, list):
        return [_redact(item, key_hint) for item in value]
    if key_hint and _is_sensitive_key(key_hint) and value not in (None, ""):
        return REDACTED
    return value


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower().replace("-", "_")
    return any(part in key_lower for part in SENSITIVE_KEY_PARTS)
