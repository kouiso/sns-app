"""Strict, side-effect-free validation for the D4 candidate's public runtime input.

This module validates one declared JSON value against controller-owned bindings.  It
does not read files, environment variables, network services, or a database, and it
does not establish formal A5 isolation.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import re
import uuid
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit


PUBLIC_FIELDS = (
    "EXPO_PUBLIC_SUPABASE_URL",
    "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
    "EXPO_PUBLIC_AUTH_RETURN_BASE",
    "EXPO_PUBLIC_AUTH_TRIAL_LAN_HOST",
    "EXPO_PUBLIC_RLS_TRIAL_POST_IDS",
)
_TOP_FIELDS = frozenset(
    {"version", "run_id", "chapter_sha256", "start_sha256", "public"}
)
_PUBLIC_FIELD_SET = frozenset(PUBLIC_FIELDS)
_HEX_RUN = re.compile(r"^[0-9a-f]{16,64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DNS_HOST = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_PUBLISHABLE_KEY = re.compile(r"^sb_publishable_[A-Za-z0-9_-]+$")
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_RFC1918 = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


class RuntimeInputError(ValueError):
    """Raised when declared input or its trusted binding fails closed."""


@dataclass(frozen=True, slots=True)
class TrustedBinding:
    run_id: str
    chapter_sha256: str
    start_sha256: str
    supabase_url: str
    publishable_key: str
    auth_return_base: str
    lan_host: str
    post_ids: tuple[str, str]


@dataclass(frozen=True, slots=True)
class ValidatedRuntimeInput:
    env: Mapping[str, str]
    public_receipt: Mapping[str, object]


def _reject_constant(_: str) -> None:
    raise RuntimeInputError("non-standard JSON number")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise RuntimeInputError("duplicate JSON field")
        value[key] = item
    return value


def _closed(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeInputError(f"{label} must contain its exact declared fields")
    return value


def _reject_control_characters(value: object) -> None:
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if _CONTROL_CHARACTERS.search(item):
                raise RuntimeInputError("control characters are forbidden")
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def _string(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or _CONTROL_CHARACTERS.search(value)
    ):
        raise RuntimeInputError(f"{label} must be a non-empty exact string")
    return value


def _run_id(value: object) -> str:
    result = _string(value, "run_id")
    if not _HEX_RUN.fullmatch(result):
        raise RuntimeInputError("run_id must be 16-64 lowercase hex characters")
    return result


def _digest(value: object, label: str) -> str:
    result = _string(value, label)
    if not _SHA256.fullmatch(result):
        raise RuntimeInputError(f"{label} must be a lowercase SHA-256 digest")
    return result


def _local_ipv4(value: object, label: str) -> str:
    result = _string(value, label)
    try:
        address = ipaddress.ip_address(result)
    except ValueError as exc:
        raise RuntimeInputError(f"{label} must be a local IPv4 address") from exc
    if not isinstance(address, ipaddress.IPv4Address) or not (
        address.is_loopback or any(address in network for network in _RFC1918)
    ):
        raise RuntimeInputError(f"{label} must be loopback or RFC1918 IPv4")
    return str(address)


def _split_url(value: object, label: str):
    result = _string(value, label)
    if any(character.isspace() for character in result):
        raise RuntimeInputError(f"{label} must not contain whitespace")
    if "?" in result or "#" in result:
        raise RuntimeInputError(f"{label} contains a forbidden URL component")
    try:
        parsed = urlsplit(result)
        _ = parsed.port
    except ValueError as exc:
        raise RuntimeInputError(f"{label} is not a valid URL") from exc
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeInputError(f"{label} contains a forbidden URL component")
    return result, parsed


def _supabase_url(value: object) -> str:
    result, parsed = _split_url(value, "EXPO_PUBLIC_SUPABASE_URL")
    if parsed.path not in ("", "/"):
        raise RuntimeInputError("Supabase URL must not contain an API path")
    if parsed.scheme == "https":
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            if not _DNS_HOST.fullmatch(parsed.hostname):
                raise RuntimeInputError("Supabase HTTPS host is invalid")
        return result
    if parsed.scheme != "http":
        raise RuntimeInputError("Supabase URL must use HTTPS or controlled local HTTP")
    _local_ipv4(parsed.hostname, "Supabase HTTP host")
    return result


def _return_base(value: object, lan_host: str) -> str:
    result, parsed = _split_url(value, "EXPO_PUBLIC_AUTH_RETURN_BASE")
    if parsed.scheme != "exp" or parsed.path != "/--/auth/return":
        raise RuntimeInputError("auth return base must use the declared Expo callback path")
    if parsed.hostname != lan_host:
        raise RuntimeInputError("auth return host must match the declared LAN host")
    return result


def _decode_jwt_payload(value: str) -> dict[str, Any]:
    parts = value.split(".")
    if len(parts) != 3 or not all(parts) or not all(_BASE64URL.fullmatch(part) for part in parts):
        raise RuntimeInputError("legacy public key must be a JWT")
    try:
        payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        payload = json.loads(
            payload_bytes.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except RuntimeInputError:
        raise
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise RuntimeInputError("legacy public key has an invalid JWT payload") from exc
    if not isinstance(payload, dict):
        raise RuntimeInputError("legacy public key has an invalid JWT payload")
    return payload


def _public_key(value: object) -> tuple[str, str]:
    result = _string(value, "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    lowered = result.lower()
    if lowered.startswith("sb_secret_") or "service_role" in lowered:
        raise RuntimeInputError("private Supabase keys are forbidden")
    if _PUBLISHABLE_KEY.fullmatch(result):
        return result, "publishable"
    payload = _decode_jwt_payload(result)
    role = payload.get("role")
    if role in ("service_role", "authenticated"):
        raise RuntimeInputError("non-anon JWT roles are forbidden")
    if role != "anon":
        raise RuntimeInputError("legacy public key must have role anon")
    return result, "legacy_anon_jwt"


def _post_ids(value: object) -> tuple[tuple[str, str], str]:
    result = _string(value, "EXPO_PUBLIC_RLS_TRIAL_POST_IDS")
    parts = result.split(",")
    if len(parts) != 2:
        raise RuntimeInputError("exactly two post IDs are required")
    try:
        parsed = tuple(uuid.UUID(part) for part in parts)
    except (ValueError, AttributeError) as exc:
        raise RuntimeInputError("post IDs must be UUIDs") from exc
    if any(identifier.version not in range(1, 6) or identifier.variant != uuid.RFC_4122 for identifier in parsed):
        raise RuntimeInputError("post IDs must use RFC 4122 UUID versions 1-5")
    normalized = tuple(str(identifier) for identifier in parsed)
    if len(set(normalized)) != 2 or result != ",".join(normalized):
        raise RuntimeInputError("post IDs must be distinct canonical UUIDs")
    return (normalized[0], normalized[1]), result


def _validate_binding(binding: TrustedBinding) -> tuple[dict[str, str], str]:
    if not isinstance(binding, TrustedBinding):
        raise RuntimeInputError("trusted binding has the wrong type")
    run_id = _run_id(binding.run_id)
    chapter = _digest(binding.chapter_sha256, "chapter_sha256")
    start = _digest(binding.start_sha256, "start_sha256")
    lan_host = _local_ipv4(binding.lan_host, "trusted LAN host")
    url = _supabase_url(binding.supabase_url)
    key, key_kind = _public_key(binding.publishable_key)
    callback = _return_base(binding.auth_return_base, lan_host)
    if (
        not isinstance(binding.post_ids, tuple)
        or len(binding.post_ids) != 2
        or not all(isinstance(identifier, str) for identifier in binding.post_ids)
    ):
        raise RuntimeInputError("trusted binding must contain exactly two string post IDs")
    post_ids, post_value = _post_ids(",".join(binding.post_ids))
    expected = {
        "EXPO_PUBLIC_SUPABASE_URL": url,
        "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY": key,
        "EXPO_PUBLIC_AUTH_RETURN_BASE": callback,
        "EXPO_PUBLIC_AUTH_TRIAL_LAN_HOST": lan_host,
        "EXPO_PUBLIC_RLS_TRIAL_POST_IDS": post_value,
        "run_id": run_id,
        "chapter_sha256": chapter,
        "start_sha256": start,
    }
    if post_ids != binding.post_ids:
        raise RuntimeInputError("trusted post IDs must already be canonical")
    return expected, key_kind


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_declared_public_runtime_input(
    raw_json: str | bytes, binding: TrustedBinding
) -> ValidatedRuntimeInput:
    """Validate declared JSON against a separately supplied trusted binding."""

    expected, expected_key_kind = _validate_binding(binding)
    if isinstance(raw_json, bytes):
        try:
            source = raw_json.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeInputError("runtime input must be UTF-8 JSON") from exc
    elif isinstance(raw_json, str):
        source = raw_json
    else:
        raise RuntimeInputError("runtime input must be JSON text")
    try:
        parsed = json.loads(
            source,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except RuntimeInputError:
        raise
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise RuntimeInputError("runtime input must be strict JSON") from exc
    _reject_control_characters(parsed)
    top = _closed(parsed, _TOP_FIELDS, "runtime input")
    if type(top["version"]) is not int or top["version"] != 1:
        raise RuntimeInputError("version must be integer 1")
    run_id = _run_id(top["run_id"])
    chapter = _digest(top["chapter_sha256"], "chapter_sha256")
    start = _digest(top["start_sha256"], "start_sha256")
    public = _closed(top["public"], _PUBLIC_FIELD_SET, "public input")
    for field in PUBLIC_FIELDS:
        _string(public[field], field)

    lan_host = _local_ipv4(public["EXPO_PUBLIC_AUTH_TRIAL_LAN_HOST"], "LAN host")
    supabase_url = _supabase_url(public["EXPO_PUBLIC_SUPABASE_URL"])
    auth_return_base = _return_base(public["EXPO_PUBLIC_AUTH_RETURN_BASE"], lan_host)
    key, key_kind = _public_key(public["EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY"])
    _, post_value = _post_ids(public["EXPO_PUBLIC_RLS_TRIAL_POST_IDS"])
    env: dict[str, str] = {
        "EXPO_PUBLIC_SUPABASE_URL": supabase_url,
        "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY": key,
        "EXPO_PUBLIC_AUTH_RETURN_BASE": auth_return_base,
        "EXPO_PUBLIC_AUTH_TRIAL_LAN_HOST": lan_host,
        "EXPO_PUBLIC_RLS_TRIAL_POST_IDS": post_value,
    }

    supplied = {**env, "run_id": run_id, "chapter_sha256": chapter, "start_sha256": start}
    if any(supplied[field] != expected[field] for field in supplied):
        raise RuntimeInputError("runtime input does not match the trusted binding")
    if key_kind != expected_key_kind:
        raise RuntimeInputError("runtime key kind does not match the trusted binding")

    hashes = MappingProxyType({field: _sha256(env[field]) for field in PUBLIC_FIELDS})
    source_bindings = MappingProxyType(
        {"chapter_sha256": chapter, "start_sha256": start}
    )
    receipt = MappingProxyType(
        {
            "schema": "d4-public-runtime-input-receipt-v1",
            "scope": "D4_DECLARED_PUBLIC_RUNTIME_INPUT_CANDIDATE",
            "key_kind": key_kind,
            "run_id": run_id,
            "source_bindings": source_bindings,
            "supplied_fieldnames": PUBLIC_FIELDS,
            "value_sha256": hashes,
        }
    )
    return ValidatedRuntimeInput(MappingProxyType(env), receipt)
