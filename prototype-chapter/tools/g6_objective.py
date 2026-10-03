"""Independent, non-formal objective checks for a future G6 exec runner.

The objective and capture inputs belong to a trusted controller and must not be
visible in the model workspace.  JSON shape validation is not evidence that a
UI observation is true: only an out-of-workspace capture accepted by the
controller's ``observation_verifier`` is treated as verified.  Even then this
component returns ``NOT_READY`` because it is not connected to the formal G6
runner, a model executor, or a real UI capture process.
"""
from __future__ import annotations

import hashlib
import json
import stat
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from g6_broker import snapshot_digest


class ObjectiveError(ValueError):
    """Raised when independent completion evidence fails closed."""


ObservationVerifier = Callable[[Path, bytes, Mapping[str, Any]], bool]

OBJECTIVE_SCOPE = "G6_OBJECTIVE_COMPONENT_NON_FORMAL"
OBSERVER_SCOPE = "G6_TRUSTED_OBSERVER_CAPTURE_V1"
BROKER_PROBE_SCOPE = "G6_BROKER_PROBE_COMPONENT_NON_FORMAL"
SUPPORTED_OBSERVATIONS = {"ui-live-reload-after-save"}

_HEX_LENGTH = 64
_TOP_KEYS = {
    "version",
    "scope",
    "run_id",
    "timing",
    "chapter",
    "start",
    "broker",
    "expected_actions",
    "artifact_stages",
    "observations",
}
_TIMING_KEYS = {"not_before_epoch", "max_age_seconds"}
_CHAPTER_KEYS = {"id", "path", "sha256"}
_TREE_KEYS = {
    "files",
    "directories",
    "broker_snapshot_sha256",
    "tree_sha256",
}
_FILE_KEYS = {"path", "sha256"}
_BROKER_KEYS = {
    "scope",
    "manifest_sha256",
    "broker_source_sha256",
    "probe_source_sha256",
    "operation_table_sha256",
    "bwrap_sha256",
    "kernel_release_sha256",
    "sandbox_recipe_sha256",
}
_EXPECTED_ACTION_KEYS = {"id", "operation", "kind"}
_STAGE_KEYS = _TREE_KEYS | {
    "id",
    "after_action",
    "final",
    "must_differ_from_start",
}
_OBSERVATION_KEYS = {"id", "kind", "stage", "expectation_sha256"}
_RECEIPT_KEYS = {"trace", "trace_sha256"}
_RECEIPT_OPTIONAL_KEYS = {"captured_at_utc"}
_TRACE_KEYS = {
    "schema",
    "scope",
    "claims",
    "artifact_id",
    "manifest_sha256",
    "chapter_sha256",
    "start_snapshot_sha256",
    "artifact_snapshot_sha256",
    "artifact_directories",
    "artifact_tree_sha256",
    "broker_source_sha256",
    "probe_source_sha256",
    "operation_table_sha256",
    "bwrap_sha256",
    "kernel_release_sha256",
    "sandbox_recipe_sha256",
    "preflight",
    "actions",
}
_CLAIM_KEYS = {
    "formal_g6_exec",
    "knowledge_isolation",
    "ui_validated",
    "a0_chapter_execution",
    "model_mcp_connected",
}
_PREFLIGHT_KEYS = {
    "clean_environment",
    "host_paths_hidden",
    "network_blocked",
    "pid_namespace",
    "private_home",
    "toolchain_read_only",
    "uts_namespace",
}
_ACTION_COMMON_KEYS = {"id", "operation", "kind"}
_ACTION_EXTRA_KEYS = {
    "mkdir": set(),
    "write": {"content_sha256"},
    "command": {"argv_sha256", "exit_code", "stdout_sha256", "stderr_sha256"},
}
_OBSERVER_RECEIPT_KEYS = {
    "version",
    "scope",
    "observer_id",
    "run_id",
    "captured_at_epoch",
    "chapter_sha256",
    "start_snapshot_sha256",
    "trace_sha256",
    "artifact_stage_hashes",
    "observations",
}
_OBSERVED_ITEM_KEYS = {
    "id",
    "kind",
    "expectation_sha256",
    "evidence_sha256",
    "status",
}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ObjectiveError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ObjectiveError(f"invalid JSON constant: {value}")


def _load_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ObjectiveError(f"{label} must be a regular, non-symlink file")
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObjectiveError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ObjectiveError(f"{label} must be an object")
    return value, raw


def _closed(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ObjectiveError(f"{label} must be an object")
    missing = keys - value.keys()
    extra = value.keys() - keys
    if missing or extra:
        raise ObjectiveError(
            f"{label} fields differ: missing={sorted(missing)} extra={sorted(extra)}"
        )
    return value


def _closed_with_optional(
    value: object, required: set[str], optional: set[str], label: str
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ObjectiveError(f"{label} must be an object")
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing or extra:
        raise ObjectiveError(
            f"{label} fields differ: missing={sorted(missing)} extra={sorted(extra)}"
        )
    return value


def _strict_int(value: object, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ObjectiveError(f"{label} must be an integer >= {minimum}")
    return value


def _identifier(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or any(not (char.isascii() and (char.isalnum() or char in "-_")) for char in value)
    ):
        raise ObjectiveError(f"{label} is invalid")
    return value


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _HEX_LENGTH
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ObjectiveError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _safe_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ObjectiveError(f"{label} must be a non-empty relative POSIX path")
    if "\\" in value or ":" in value or any(ord(char) < 32 for char in value):
        raise ObjectiveError(f"unsafe {label}: {value!r}")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or value != parsed.as_posix():
        raise ObjectiveError(f"unsafe {label}: {value!r}")
    if any(part in {"", ".", ".."} for part in parsed.parts):
        raise ObjectiveError(f"unsafe {label}: {value!r}")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def artifact_tree_digest(
    files: list[tuple[str, bytes]], directories: list[str]
) -> str:
    """Hash exact file contents and the explicit directory set."""
    return _sha256(
        _canonical(
            {
                "files_sha256": snapshot_digest(
                    sorted(files, key=lambda item: PurePosixPath(item[0]))
                ),
                "directories": sorted(directories),
            }
        )
    )


def _regular_file(root: Path, relative: str, label: str) -> bytes:
    if root.is_symlink() or not root.is_dir():
        raise ObjectiveError(f"{label} root must be a non-symlink directory")
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise ObjectiveError(f"missing {label}: {relative}") from exc
        if stat.S_ISLNK(mode):
            raise ObjectiveError(f"symlink is forbidden in {label}: {relative}")
    if not stat.S_ISREG(mode):
        raise ObjectiveError(f"{label} is not a regular file: {relative}")
    try:
        return current.read_bytes()
    except OSError as exc:
        raise ObjectiveError(f"cannot read {label}: {relative}") from exc


def _read_tree(root: Path, label: str) -> tuple[list[tuple[str, bytes]], list[str]]:
    if root.is_symlink() or not root.is_dir():
        raise ObjectiveError(f"{label} root must be a non-symlink directory")
    files: list[tuple[str, bytes]] = []
    directories: list[str] = []
    try:
        paths = sorted(root.rglob("*"))
    except OSError as exc:
        raise ObjectiveError(f"cannot enumerate {label} root") from exc
    for path in paths:
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ObjectiveError(f"symlink is forbidden in {label}: {relative}")
        if stat.S_ISDIR(mode):
            directories.append(relative)
        elif stat.S_ISREG(mode):
            files.append((relative, path.read_bytes()))
        else:
            raise ObjectiveError(f"unsupported entry in {label}: {relative}")
    return files, directories


def _parse_file_specs(value: object, label: str) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        raise ObjectiveError(f"{label} must be an array")
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item = _closed(raw, _FILE_KEYS, f"{label}[{index}]")
        path = _safe_path(item["path"], f"{label}[{index}].path")
        if path in seen:
            raise ObjectiveError(f"duplicate expected file: {path}")
        seen.add(path)
        result.append((path, _digest(item["sha256"], f"{label}[{index}].sha256")))
    return sorted(result)


def _parse_directories(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ObjectiveError(f"{label} must be an array")
    result = [_safe_path(item, f"{label} entry") for item in value]
    if len(result) != len(set(result)):
        raise ObjectiveError(f"{label} contains duplicates")
    return sorted(result)


def _validate_tree(
    spec: Mapping[str, Any], root: Path, label: str
) -> tuple[str, str]:
    expected_files = _parse_file_specs(spec["files"], f"{label}.files")
    expected_directories = _parse_directories(
        spec["directories"], f"{label}.directories"
    )
    files, directories = _read_tree(root, label)
    actual_files = sorted((path, _sha256(data)) for path, data in files)
    if actual_files != expected_files or sorted(directories) != expected_directories:
        raise ObjectiveError(f"{label} tree differs from the closed objective")
    broker_snapshot = snapshot_digest(files)
    tree_digest = artifact_tree_digest(files, directories)
    if broker_snapshot != _digest(
        spec["broker_snapshot_sha256"], f"{label}.broker_snapshot_sha256"
    ):
        raise ObjectiveError(f"{label} broker snapshot hash mismatch")
    if tree_digest != _digest(spec["tree_sha256"], f"{label}.tree_sha256"):
        raise ObjectiveError(f"{label} tree hash mismatch")
    return broker_snapshot, tree_digest


def _validate_fresh_file(
    path: Path, timing: Mapping[str, Any], now_epoch: int, label: str
) -> None:
    not_before = _strict_int(timing["not_before_epoch"], "timing.not_before_epoch")
    max_age = _strict_int(timing["max_age_seconds"], "timing.max_age_seconds", 1)
    modified = path.stat().st_mtime
    if modified < not_before or modified > now_epoch + 5 or now_epoch - modified > max_age:
        raise ObjectiveError(f"{label} is stale or outside the run window")


def validate_broker_receipt_schema(
    receipt_path: Path,
) -> tuple[dict[str, Any], str]:
    """Validate the current broker producer schema without claiming completion."""
    receipt, _ = _load_json(receipt_path, "broker receipt")
    receipt = _closed_with_optional(
        receipt, _RECEIPT_KEYS, _RECEIPT_OPTIONAL_KEYS, "broker receipt"
    )
    if "captured_at_utc" in receipt and (
        not isinstance(receipt["captured_at_utc"], str)
        or not receipt["captured_at_utc"].strip()
    ):
        raise ObjectiveError("captured_at_utc must be a non-empty string")
    trace = _closed(receipt["trace"], _TRACE_KEYS, "broker trace")
    trace_digest = _sha256(_canonical(trace))
    if trace_digest != _digest(receipt["trace_sha256"], "trace_sha256"):
        raise ObjectiveError("broker trace hash mismatch")
    if trace["schema"] != "g6-broker-trace-v1":
        raise ObjectiveError("unsupported broker trace schema")
    if trace["scope"] != BROKER_PROBE_SCOPE:
        raise ObjectiveError("unsupported broker trace scope")
    _identifier(trace["artifact_id"], "trace.artifact_id")
    for field in (
        "manifest_sha256",
        "chapter_sha256",
        "start_snapshot_sha256",
        "artifact_snapshot_sha256",
        "artifact_tree_sha256",
        "broker_source_sha256",
        "probe_source_sha256",
        "operation_table_sha256",
        "bwrap_sha256",
        "kernel_release_sha256",
        "sandbox_recipe_sha256",
    ):
        _digest(trace[field], f"trace.{field}")
    directories = _parse_directories(
        trace["artifact_directories"], "trace.artifact_directories"
    )
    expected_tree_hash = _sha256(
        _canonical(
            {
                "files_sha256": trace["artifact_snapshot_sha256"],
                "directories": directories,
            }
        )
    )
    if trace["artifact_tree_sha256"] != expected_tree_hash:
        raise ObjectiveError("broker artifact tree hash mismatch")
    claims = _closed(trace["claims"], _CLAIM_KEYS, "broker trace claims")
    if any(claims[key] is not False for key in _CLAIM_KEYS):
        raise ObjectiveError("broker probe may not claim formal, model, A0, knowledge, or UI proof")
    preflight = _closed(trace["preflight"], _PREFLIGHT_KEYS, "broker preflight")
    if any(preflight[key] is not True for key in _PREFLIGHT_KEYS):
        raise ObjectiveError("broker preflight is not 7/7")
    raw_actions = trace["actions"]
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ObjectiveError("broker trace actions must be non-empty")
    for index, raw in enumerate(raw_actions):
        if not isinstance(raw, dict):
            raise ObjectiveError(f"trace.actions[{index}] must be an object")
        kind = raw.get("kind")
        if kind not in _ACTION_EXTRA_KEYS:
            raise ObjectiveError(f"unsupported trace action kind: {kind!r}")
        item = _closed(
            raw,
            _ACTION_COMMON_KEYS | _ACTION_EXTRA_KEYS[kind],
            f"trace.actions[{index}]",
        )
        _identifier(item["id"], f"trace.actions[{index}].id")
        _identifier(item["operation"], f"trace.actions[{index}].operation")
        if kind == "command":
            if type(item["exit_code"]) is not int or item["exit_code"] != 0:
                raise ObjectiveError(f"command action did not succeed: {item['id']}")
            for field in ("argv_sha256", "stdout_sha256", "stderr_sha256"):
                _digest(item[field], f"trace.actions[{index}].{field}")
        elif kind == "write":
            _digest(item["content_sha256"], f"trace.actions[{index}].content_sha256")
    return trace, trace_digest


def _validate_trace(
    receipt_path: Path,
    objective: Mapping[str, Any],
    now_epoch: int,
) -> tuple[dict[str, Any], str]:
    trace, trace_digest = validate_broker_receipt_schema(receipt_path)
    _validate_fresh_file(receipt_path, objective["timing"], now_epoch, "broker receipt")
    if trace["scope"] != objective["broker"]["scope"]:
        raise ObjectiveError("broker trace scope mismatch")
    if _identifier(trace["artifact_id"], "trace.artifact_id") != objective["run_id"]:
        raise ObjectiveError("broker trace is not bound to this run_id")

    broker = _closed(objective["broker"], _BROKER_KEYS, "objective broker")
    if broker["scope"] != BROKER_PROBE_SCOPE:
        raise ObjectiveError("only the non-formal broker probe scope is supported")
    for field in _BROKER_KEYS:
        expected = broker[field]
        if field == "scope":
            if not isinstance(expected, str) or trace[field] != expected:
                raise ObjectiveError("broker scope mismatch")
        elif trace[field] != _digest(expected, f"broker.{field}"):
            raise ObjectiveError(f"broker binding mismatch: {field}")

    chapter = _closed(objective["chapter"], _CHAPTER_KEYS, "chapter")
    start = _closed(objective["start"], _TREE_KEYS, "start")
    if trace["chapter_sha256"] != _digest(chapter["sha256"], "chapter.sha256"):
        raise ObjectiveError("trace chapter hash mismatch")
    if trace["start_snapshot_sha256"] != _digest(
        start["broker_snapshot_sha256"], "start.broker_snapshot_sha256"
    ):
        raise ObjectiveError("trace start hash mismatch")

    expected_actions = objective["expected_actions"]
    if not isinstance(expected_actions, list) or not expected_actions:
        raise ObjectiveError("expected_actions must be a non-empty array")
    expected_order: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(expected_actions):
        item = _closed(raw, _EXPECTED_ACTION_KEYS, f"expected_actions[{index}]")
        action_id = _identifier(item["id"], f"expected_actions[{index}].id")
        operation = _identifier(
            item["operation"], f"expected_actions[{index}].operation"
        )
        kind = item["kind"]
        if kind not in _ACTION_EXTRA_KEYS:
            raise ObjectiveError(f"unsupported action kind: {kind!r}")
        if action_id in seen:
            raise ObjectiveError(f"duplicate expected action id: {action_id}")
        seen.add(action_id)
        expected_order.append((action_id, operation, kind))

    raw_actions = trace["actions"]
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ObjectiveError("broker trace actions must be non-empty")
    actual_order: list[tuple[str, str, str]] = []
    for index, raw in enumerate(raw_actions):
        if not isinstance(raw, dict):
            raise ObjectiveError(f"trace.actions[{index}] must be an object")
        kind = raw.get("kind")
        if kind not in _ACTION_EXTRA_KEYS:
            raise ObjectiveError(f"unsupported trace action kind: {kind!r}")
        item = _closed(
            raw,
            _ACTION_COMMON_KEYS | _ACTION_EXTRA_KEYS[kind],
            f"trace.actions[{index}]",
        )
        action_id = _identifier(item["id"], f"trace.actions[{index}].id")
        operation = _identifier(item["operation"], f"trace.actions[{index}].operation")
        if kind == "command":
            if type(item["exit_code"]) is not int or item["exit_code"] != 0:
                raise ObjectiveError(f"command action did not succeed: {action_id}")
            for field in ("argv_sha256", "stdout_sha256", "stderr_sha256"):
                _digest(item[field], f"trace.actions[{index}].{field}")
        elif kind == "write":
            _digest(item["content_sha256"], f"trace.actions[{index}].content_sha256")
        actual_order.append((action_id, operation, kind))
    if actual_order != expected_order:
        raise ObjectiveError("required actions are missing, extra, or out of order")
    return trace, trace_digest


def validate_artifact_stages_only(
    start_spec: Mapping[str, Any],
    start_root: Path,
    artifact_stages: object,
    artifact_roots: Mapping[str, Path],
) -> dict[str, Any]:
    """Validate actual trees while making no action, UI, or formal-G6 claim."""
    start = _closed(start_spec, _TREE_KEYS, "start")
    start_snapshot, start_tree_hash = _validate_tree(start, start_root, "start")
    if not isinstance(artifact_stages, list) or not artifact_stages:
        raise ObjectiveError("artifact_stages must be a non-empty array")
    resolved_roots = [root.resolve() for root in artifact_roots.values()]
    if len(resolved_roots) != len(set(resolved_roots)):
        raise ObjectiveError("artifact stage roots must be distinct")
    for index, root in enumerate(resolved_roots):
        for other in resolved_roots[index + 1 :]:
            if root.is_relative_to(other) or other.is_relative_to(root):
                raise ObjectiveError("artifact stage roots must not contain each other")

    stage_bindings: dict[str, dict[str, Any]] = {}
    final_stages: list[str] = []
    for index, raw_stage in enumerate(artifact_stages):
        stage = _closed(raw_stage, _STAGE_KEYS, f"artifact_stages[{index}]")
        stage_id = _identifier(stage["id"], f"artifact_stages[{index}].id")
        _identifier(stage["after_action"], f"artifact_stages[{index}].after_action")
        if stage_id in stage_bindings or stage_id not in artifact_roots:
            raise ObjectiveError(f"missing or duplicate artifact stage root: {stage_id}")
        if (
            type(stage["final"]) is not bool
            or type(stage["must_differ_from_start"]) is not bool
        ):
            raise ObjectiveError("artifact stage flags must be boolean")
        if stage["must_differ_from_start"] is not True:
            raise ObjectiveError("every artifact stage must reject start=final")
        snapshot, tree_hash = _validate_tree(
            stage, artifact_roots[stage_id], stage_id
        )
        if snapshot == start_snapshot:
            raise ObjectiveError(f"artifact stage equals the start snapshot: {stage_id}")
        stage_bindings[stage_id] = {
            "broker_snapshot_sha256": snapshot,
            "tree_sha256": tree_hash,
            "directories": _parse_directories(
                stage["directories"], f"artifact_stages[{index}].directories"
            ),
        }
        if stage["final"]:
            final_stages.append(stage_id)
    if set(artifact_roots) != set(stage_bindings):
        raise ObjectiveError("artifact stage roots contain unknown entries")
    if len(final_stages) != 1:
        raise ObjectiveError("exactly one artifact stage must be final")
    if final_stages[0] != artifact_stages[-1]["id"]:
        raise ObjectiveError("the final artifact stage must be last")
    return {
        "scope": OBJECTIVE_SCOPE,
        "status": "ARTIFACT_ONLY_VALIDATED_NON_FORMAL",
        "claims": {"actions": False, "ui": False, "formal_g6_exec": False},
        "bindings": {
            "start_broker_snapshot_sha256": start_snapshot,
            "start_tree_sha256": start_tree_hash,
            "artifact_stages": stage_bindings,
            "final_stage": final_stages[0],
        },
    }


def _validate_observation(
    observation_path: Path,
    verifier: ObservationVerifier,
    objective: Mapping[str, Any],
    trace_digest: str,
    stage_hashes: Mapping[str, str],
    forbidden_roots: list[Path],
    now_epoch: int,
) -> None:
    observation_resolved = observation_path.resolve()
    if any(
        observation_resolved == root.resolve()
        or observation_resolved.is_relative_to(root.resolve())
        for root in forbidden_roots
    ):
        raise ObjectiveError("UI receipt must be outside model/start/artifact roots")
    receipt, raw = _load_json(observation_path, "UI observation receipt")
    receipt = _closed(receipt, _OBSERVER_RECEIPT_KEYS, "UI observation receipt")
    if type(receipt["version"]) is not int or receipt["version"] != 1:
        raise ObjectiveError("UI observation version must be integer 1")
    if receipt["scope"] != OBSERVER_SCOPE:
        raise ObjectiveError("UI observation scope mismatch")
    _identifier(receipt["observer_id"], "observer_id")
    captured = _strict_int(receipt["captured_at_epoch"], "captured_at_epoch")
    timing = _closed(objective["timing"], _TIMING_KEYS, "timing")
    not_before = _strict_int(timing["not_before_epoch"], "timing.not_before_epoch")
    max_age = _strict_int(timing["max_age_seconds"], "timing.max_age_seconds", 1)
    if captured < not_before or captured > now_epoch + 5 or now_epoch - captured > max_age:
        raise ObjectiveError("UI observation is stale or outside the run window")
    _validate_fresh_file(observation_path, timing, now_epoch, "UI observation receipt")
    if receipt["run_id"] != objective["run_id"]:
        raise ObjectiveError("UI observation run_id mismatch")
    chapter = objective["chapter"]
    start = objective["start"]
    if receipt["chapter_sha256"] != chapter["sha256"]:
        raise ObjectiveError("UI observation chapter binding mismatch")
    if receipt["start_snapshot_sha256"] != start["broker_snapshot_sha256"]:
        raise ObjectiveError("UI observation start binding mismatch")
    if receipt["trace_sha256"] != trace_digest:
        raise ObjectiveError("UI observation trace binding mismatch")
    raw_stage_hashes = receipt["artifact_stage_hashes"]
    if not isinstance(raw_stage_hashes, dict) or raw_stage_hashes != dict(stage_hashes):
        raise ObjectiveError("UI observation artifact-stage binding mismatch")

    expected_observations = objective["observations"]
    actual_observations = receipt["observations"]
    if not isinstance(actual_observations, list):
        raise ObjectiveError("UI observations must be an array")
    expected: list[tuple[str, str, str]] = []
    for index, raw_spec in enumerate(expected_observations):
        spec = _closed(raw_spec, _OBSERVATION_KEYS, f"observations[{index}]")
        observation_id = _identifier(spec["id"], f"observations[{index}].id")
        kind = spec["kind"]
        if kind not in SUPPORTED_OBSERVATIONS:
            raise ObjectiveError(f"unsupported observation kind: {kind!r}")
        if spec["stage"] not in stage_hashes:
            raise ObjectiveError(f"unknown observation stage: {spec['stage']!r}")
        expected.append(
            (
                observation_id,
                kind,
                _digest(
                    spec["expectation_sha256"],
                    f"observations[{index}].expectation_sha256",
                ),
            )
        )
    actual: list[tuple[str, str, str]] = []
    for index, raw_item in enumerate(actual_observations):
        item = _closed(raw_item, _OBSERVED_ITEM_KEYS, f"UI observations[{index}]")
        if item["status"] != "observed":
            raise ObjectiveError("UI observation status is not observed")
        _digest(item["evidence_sha256"], f"UI observations[{index}].evidence_sha256")
        actual.append(
            (
                _identifier(item["id"], f"UI observations[{index}].id"),
                item["kind"],
                _digest(
                    item["expectation_sha256"],
                    f"UI observations[{index}].expectation_sha256",
                ),
            )
        )
    if actual != expected:
        raise ObjectiveError("UI observations are missing, extra, or out of order")
    if verifier(observation_path, raw, receipt) is not True:
        raise ObjectiveError("trusted UI observer rejected the capture evidence")


def evaluate_objective(
    objective_path: Path,
    broker_receipt_path: Path,
    trusted_input_root: Path,
    start_root: Path,
    artifact_roots: Mapping[str, Path],
    *,
    observation_path: Path | None = None,
    observation_verifier: ObservationVerifier | None = None,
    now_epoch: int | None = None,
) -> dict[str, Any]:
    """Validate component evidence without claiming formal G6 completion."""
    now = int(time.time()) if now_epoch is None else _strict_int(now_epoch, "now_epoch")
    objective, _ = _load_json(objective_path, "objective")
    objective = _closed(objective, _TOP_KEYS, "objective")
    if type(objective["version"]) is not int or objective["version"] != 1:
        raise ObjectiveError("objective version must be integer 1")
    if objective["scope"] != OBJECTIVE_SCOPE:
        raise ObjectiveError("objective scope mismatch")
    _identifier(objective["run_id"], "run_id")
    timing = _closed(objective["timing"], _TIMING_KEYS, "timing")
    _strict_int(timing["not_before_epoch"], "timing.not_before_epoch")
    _strict_int(timing["max_age_seconds"], "timing.max_age_seconds", 1)
    protected_roots = (start_root, *artifact_roots.values())
    for protected_path, label in (
        (objective_path, "objective"),
        (broker_receipt_path, "broker receipt"),
        *(([(observation_path, "UI receipt")] if observation_path is not None else [])),
    ):
        protected_resolved = protected_path.resolve()
        if any(
            protected_resolved == root.resolve()
            or protected_resolved.is_relative_to(root.resolve())
            for root in protected_roots
        ):
            raise ObjectiveError(
                f"{label} must be outside model/start/artifact roots"
            )

    chapter = _closed(objective["chapter"], _CHAPTER_KEYS, "chapter")
    _identifier(chapter["id"], "chapter.id")
    chapter_path = _safe_path(chapter["path"], "chapter.path")
    chapter_bytes = _regular_file(trusted_input_root, chapter_path, "chapter")
    if _sha256(chapter_bytes) != _digest(chapter["sha256"], "chapter.sha256"):
        raise ObjectiveError("chapter file hash mismatch")

    start = _closed(objective["start"], _TREE_KEYS, "start")
    artifact_result = validate_artifact_stages_only(
        start, start_root, objective["artifact_stages"], artifact_roots
    )
    start_snapshot = artifact_result["bindings"]["start_broker_snapshot_sha256"]
    trace, trace_digest = _validate_trace(broker_receipt_path, objective, now)

    stages = objective["artifact_stages"]
    stage_bindings = artifact_result["bindings"]["artifact_stages"]
    stage_hashes = {
        stage_id: binding["tree_sha256"]
        for stage_id, binding in stage_bindings.items()
    }
    action_ids = [item["id"] for item in objective["expected_actions"]]
    last_action_index = -1
    for index, raw_stage in enumerate(stages):
        stage = _closed(raw_stage, _STAGE_KEYS, f"artifact_stages[{index}]")
        stage_id = _identifier(stage["id"], f"artifact_stages[{index}].id")
        after_action = _identifier(
            stage["after_action"], f"artifact_stages[{index}].after_action"
        )
        if after_action not in action_ids:
            raise ObjectiveError(f"unknown stage action: {after_action!r}")
        action_index = action_ids.index(after_action)
        if action_index <= last_action_index:
            raise ObjectiveError("artifact stages are not in action order")
        last_action_index = action_index
        if stage["final"]:
            if action_index != len(action_ids) - 1:
                raise ObjectiveError(
                    "the final artifact stage must follow the last required action"
                )
            if (
                stage_bindings[stage_id]["broker_snapshot_sha256"]
                != trace["artifact_snapshot_sha256"]
            ):
                raise ObjectiveError("final artifact does not match broker trace")
            if stage_bindings[stage_id]["directories"] != trace["artifact_directories"]:
                raise ObjectiveError("final artifact directories do not match broker trace")
            if stage_bindings[stage_id]["tree_sha256"] != trace["artifact_tree_sha256"]:
                raise ObjectiveError("final artifact tree does not match broker trace")

    observations = objective["observations"]
    if not isinstance(observations, list) or not observations:
        raise ObjectiveError("at least one trusted UI observation is required")
    seen_observations: set[str] = set()
    for index, raw_observation in enumerate(observations):
        observation = _closed(
            raw_observation, _OBSERVATION_KEYS, f"observations[{index}]"
        )
        observation_id = _identifier(
            observation["id"], f"observations[{index}].id"
        )
        if observation_id in seen_observations:
            raise ObjectiveError(f"duplicate observation id: {observation_id}")
        seen_observations.add(observation_id)
        if observation["kind"] not in SUPPORTED_OBSERVATIONS:
            raise ObjectiveError(
                f"unsupported observation kind: {observation['kind']!r}"
            )
        if observation["stage"] not in stage_hashes:
            raise ObjectiveError(
                f"unknown observation stage: {observation['stage']!r}"
            )
        _digest(
            observation["expectation_sha256"],
            f"observations[{index}].expectation_sha256",
        )
    ui_status = "UNSUPPORTED"
    if observation_path is not None and observation_verifier is not None:
        _validate_observation(
            observation_path,
            observation_verifier,
            objective,
            trace_digest,
            stage_hashes,
            [start_root, *artifact_roots.values()],
            now,
        )
        ui_status = "VERIFIED_BY_TRUSTED_CALLBACK"

    return {
        "scope": OBJECTIVE_SCOPE,
        "status": "NOT_READY",
        "checks": {
            "chapter": "PASS",
            "start": "PASS",
            "actions": "PASS",
            "artifact_stages": {stage_id: "PASS" for stage_id in stage_hashes},
            "ui_observation": ui_status,
        },
        "bindings": {
            "trace_sha256": trace_digest,
            "start_snapshot_sha256": start_snapshot,
            "artifact_tree_sha256": stage_hashes,
        },
        "unsupported": [
            "formal runner/model execution is not connected",
            "schema validation alone does not prove UI truth",
            "a run-once capture ledger is not connected",
        ],
    }
