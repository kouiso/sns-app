"""Fail-closed helpers for the G6 runner.

The runner deliberately treats model self-report as data, never as proof.  An
independent objective validator must set ``objective_validated`` before an exec
result can pass.
"""
from __future__ import annotations

import json
import hashlib
import re
import sys
from pathlib import Path
from typing import Any


class G6ResultError(ValueError):
    """Raised when an adapter result is not a valid G6 receipt."""


CLASSIFICATION_MARKER = "G6_HIGH_VALUE_CLASSIFICATION: complete"
ZERO_ITEMS_MARKER = "G6_HIGH_VALUE_ITEMS: 0"
ITEM_CLASSIFICATION_RE = re.compile(
    r"^\s*-\s*(?:\*\*)?G6_HIGH_VALUE(?:\*\*)?\s*:\s*"
    r"(?:\*\*)?(高|低|対象外|unobserved)(?:\*\*)?"
    r"(?:\s+—\s+.*)?\s*$"
)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise G6ResultError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise G6ResultError(f"invalid JSON constant: {value}")


def parse_result(raw: str, mode: str) -> dict[str, Any]:
    """Parse one adapter response; reject prose, missing fields, and extras."""
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise G6ResultError("adapter output is not JSON") from exc
    if not isinstance(value, dict):
        raise G6ResultError("adapter output must be an object")
    common = {"adapter"}
    if mode == "exec":
        required = common | {"r1_reached", "r2_stuck", "r3_external_knowledge", "r4_unavailable"}
        allowed = required
    elif mode == "read":
        required = common | {"choice", "reason", "boring_a", "boring_b"}
        allowed = required
    else:
        raise G6ResultError("unknown mode")
    missing = required - value.keys()
    extra = value.keys() - allowed
    if missing:
        raise G6ResultError(f"missing fields: {sorted(missing)}")
    if extra:
        raise G6ResultError(f"unexpected fields: {sorted(extra)}")
    if not isinstance(value["adapter"], str) or not value["adapter"]:
        raise G6ResultError("adapter identity is required")
    if mode == "exec":
        for field in ("r2_stuck", "r3_external_knowledge", "r4_unavailable"):
            if not isinstance(value[field], list) or not all(
                isinstance(item, str) and item.strip() for item in value[field]
            ):
                raise G6ResultError(f"{field} must be a string array")
        if not isinstance(value["r1_reached"], bool):
            raise G6ResultError("r1_reached must be boolean")
    else:
        if not isinstance(value["reason"], str) or not value["reason"].strip():
            raise G6ResultError("read reason is required")
        for field in ("boring_a", "boring_b"):
            if not isinstance(value[field], list) or not all(
                isinstance(item, str) and item.strip() for item in value[field]
            ):
                raise G6ResultError(f"{field} must be a string array")
    return value


def exec_pass(result: dict[str, Any], validator_ok: bool = False) -> bool:
    """Apply the formal exec rule after independent validation."""
    return (
        validator_ok
        and result.get("r1_reached") is True
        and result.get("r2_stuck") == []
        and result.get("r3_external_knowledge") == []
        and result.get("r4_unavailable") == []
    )


def read_choice(result: dict[str, Any]) -> str:
    choice = result.get("choice")
    if choice not in {"A", "B"}:
        raise G6ResultError("read choice must be A or B")
    return choice


def dev_log_evidence(path: Path) -> tuple[int, int, str]:
    """Return (high count, classified item count, SHA-256) for one dev log."""
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise G6ResultError(f"development log cannot be read: {path}: {exc}") from exc
    lines = text.splitlines()
    if sum(line.strip() == CLASSIFICATION_MARKER for line in lines) != 1:
        raise G6ResultError(
            f"development log must contain exactly one {CLASSIFICATION_MARKER!r}"
        )
    labels = [
        match.group(1)
        for line in lines
        if (match := ITEM_CLASSIFICATION_RE.match(line)) is not None
    ]
    zero_markers = sum(line.strip() == ZERO_ITEMS_MARKER for line in lines)
    malformed = [
        line
        for line in lines
        if "G6_HIGH_VALUE" in line
        and line.strip() not in {CLASSIFICATION_MARKER, ZERO_ITEMS_MARKER}
        and ITEM_CLASSIFICATION_RE.match(line) is None
    ]
    if malformed:
        raise G6ResultError(f"malformed G6 high-value classification: {malformed[0]}")
    if zero_markers > 1 or (zero_markers and labels):
        raise G6ResultError("G6_HIGH_VALUE_ITEMS: 0 conflicts with classified items")
    if not labels and zero_markers != 1:
        raise G6ResultError(
            "development log needs classified G6_HIGH_VALUE items or G6_HIGH_VALUE_ITEMS: 0"
        )
    legacy_value_lines = sum("教材に載せる価値" in line for line in lines)
    if legacy_value_lines > len(labels):
        raise G6ResultError("a teaching-value entry lacks an explicit G6_HIGH_VALUE label")
    high_count = labels.count("高")
    return high_count, len(labels), hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    # The shell runner uses this as an objective, fail-closed validator.
    # It intentionally emits no model content or credentials.
    try:
        mode = sys.argv[1] if len(sys.argv) >= 2 else ""
        if mode == "devlog":
            if len(sys.argv) != 3:
                raise G6ResultError("usage: g6_support.py devlog PATH")
            count, classified, digest = dev_log_evidence(Path(sys.argv[2]))
            print(f"HIGH_VALUE_COUNT={count}")
            print(f"CLASSIFIED_ITEM_COUNT={classified}")
            print(f"DEV_LOG_SHA256={digest}")
            raise SystemExit(0)
        if mode not in {"exec", "read"} or len(sys.argv) != 2:
            raise G6ResultError("usage: g6_support.py exec|read or devlog PATH")
        result = parse_result(sys.stdin.read(), mode)
        if mode == "exec":
            raise G6ResultError("independent validator artifact is required")
        if mode == "read":
            print(f"CHOICE={read_choice(result)}")
    except (G6ResultError, IndexError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
