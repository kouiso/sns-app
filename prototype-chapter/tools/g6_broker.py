"""A fail-closed, non-networked operation broker for a future G6 executor.

This probe-only module is deliberately not wired to ``g6-run.sh`` and has no
command-line entry point.  A manifest may select only operations compiled into
this module; it can never supply an argv vector or file contents.  A trusted
controller owns the process, input root, manifest, and initially empty
workspace.  Protection against a same-UID controller racing filesystem checks
is outside this component's boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final


class BrokerError(ValueError):
    """Raised when the broker cannot prove that an operation is safe."""


@dataclass(frozen=True)
class Operation:
    kind: str
    source_text: str
    path: str | None = None
    content: bytes | None = None
    argv: tuple[str, ...] = ()


# The manifest selects IDs from this table.  It cannot add commands or content.
PROBE_OPERATIONS: Final[dict[str, Operation]] = {
    "make-src-directory": Operation(
        kind="mkdir", source_text="G6_MKDIR: src\n", path="src"
    ),
    "write-broker-probe": Operation(
        kind="write",
        source_text=(
            'G6_WRITE: {"path":"src/g6-broker-probe.txt",'
            '"utf8":"G6 broker probe\\n"}\n'
        ),
        path="src/g6-broker-probe.txt",
        content=b"G6 broker probe\n",
    ),
    "read-python-version": Operation(
        kind="command",
        source_text='G6_ARGV: ["/usr/bin/python3","--version"]\n',
        argv=("/usr/bin/python3", "--version"),
    ),
}

_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_TOP_KEYS = {"version", "chapter", "start", "artifact_id", "actions"}
_FILE_KEYS = {"path", "sha256"}
_START_KEYS = {"root", "files", "snapshot_sha256"}
_ACTION_KEYS = {"id", "operation", "source"}
_SOURCE_KEYS = {"path", "start_line", "end_line", "sha256"}
BWRAP_PATH: Final = Path("/usr/bin/bwrap")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BrokerError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise BrokerError(f"invalid JSON constant: {value}")


def _closed(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BrokerError(f"{label} must be an object")
    missing = keys - value.keys()
    extra = value.keys() - keys
    if missing or extra:
        raise BrokerError(
            f"{label} fields differ: missing={sorted(missing)} extra={sorted(extra)}"
        )
    return value


def _safe_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BrokerError(f"{label} must be a non-empty relative POSIX path")
    if "\\" in value or ":" in value or any(ord(char) < 32 for char in value):
        raise BrokerError(f"unsafe {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix():
        raise BrokerError(f"unsafe {label}: {value!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise BrokerError(f"unsafe {label}: {value!r}")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _HEX.fullmatch(value) is None:
        raise BrokerError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _operation_table_digest() -> str:
    table = {
        operation_id: {
            "kind": operation.kind,
            "source_text": operation.source_text,
            "path": operation.path,
            "content_sha256": (
                _sha256(operation.content) if operation.content is not None else None
            ),
            "argv": list(operation.argv),
        }
        for operation_id, operation in sorted(PROBE_OPERATIONS.items())
    }
    return _sha256(_canonical(table))


def snapshot_digest(files: list[tuple[str, bytes]]) -> str:
    """Hash an ordered, path-bound set of files."""
    record = [{"path": path, "sha256": _sha256(data)} for path, data in files]
    return _sha256(_canonical(record))


def _read_regular(root: Path, relative: str, label: str) -> bytes:
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise BrokerError(f"cannot read {label}: {relative}") from exc
        if stat.S_ISLNK(mode):
            raise BrokerError(f"symlink is forbidden in {label}: {relative}")
    if not stat.S_ISREG(mode):
        raise BrokerError(f"{label} is not a regular file: {relative}")
    try:
        return current.read_bytes()
    except OSError as exc:
        raise BrokerError(f"cannot read {label}: {relative}") from exc


def _load_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        if path.is_symlink() or not path.is_file():
            raise BrokerError("manifest must be a regular, non-symlink file")
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BrokerError("manifest is not valid UTF-8 JSON") from exc
    return _closed(value, _TOP_KEYS, "manifest"), raw


def _validate_manifest(
    value: dict[str, Any], input_root: Path
) -> tuple[bytes, list[tuple[str, bytes]], list[dict[str, Any]]]:
    if type(value["version"]) is not int or value["version"] != 1:
        raise BrokerError("manifest version must be integer 1")
    artifact_id = value["artifact_id"]
    if not isinstance(artifact_id, str) or _ID.fullmatch(artifact_id) is None:
        raise BrokerError("artifact_id is invalid")

    chapter = _closed(value["chapter"], _FILE_KEYS, "chapter")
    chapter_path = _safe_path(chapter["path"], "chapter.path")
    chapter_digest = _digest(chapter["sha256"], "chapter.sha256")
    chapter_bytes = _read_regular(input_root, chapter_path, "chapter")
    if _sha256(chapter_bytes) != chapter_digest:
        raise BrokerError("chapter hash mismatch")
    try:
        chapter_lines = chapter_bytes.decode("utf-8").splitlines(keepends=True)
    except UnicodeError as exc:
        raise BrokerError("chapter must be UTF-8") from exc

    start = _closed(value["start"], _START_KEYS, "start")
    start_root = _safe_path(start["root"], "start.root")
    expected_snapshot = _digest(start["snapshot_sha256"], "start.snapshot_sha256")
    if not isinstance(start["files"], list) or not start["files"]:
        raise BrokerError("start.files must be a non-empty array")
    start_files: list[tuple[str, bytes]] = []
    seen_paths: set[str] = set()
    for index, raw_file in enumerate(start["files"]):
        item = _closed(raw_file, _FILE_KEYS, f"start.files[{index}]")
        relative = _safe_path(item["path"], f"start.files[{index}].path")
        if relative in seen_paths:
            raise BrokerError(f"duplicate start path: {relative}")
        seen_paths.add(relative)
        expected = _digest(item["sha256"], f"start.files[{index}].sha256")
        data = _read_regular(input_root, f"{start_root}/{relative}", "start file")
        if _sha256(data) != expected:
            raise BrokerError(f"start file hash mismatch: {relative}")
        start_files.append((relative, data))
    start_files.sort(key=lambda pair: pair[0])
    if snapshot_digest(start_files) != expected_snapshot:
        raise BrokerError("start snapshot hash mismatch")

    actions = value["actions"]
    if not isinstance(actions, list) or not actions:
        raise BrokerError("actions must be a non-empty array")
    validated_actions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_action in enumerate(actions):
        action = _closed(raw_action, _ACTION_KEYS, f"actions[{index}]")
        action_id = action["id"]
        operation_id = action["operation"]
        if not isinstance(action_id, str) or _ID.fullmatch(action_id) is None:
            raise BrokerError(f"actions[{index}].id is invalid")
        if action_id in seen_ids:
            raise BrokerError(f"duplicate action id: {action_id}")
        seen_ids.add(action_id)
        if not isinstance(operation_id, str) or operation_id not in PROBE_OPERATIONS:
            raise BrokerError(f"unknown operation: {operation_id!r}")
        source = _closed(action["source"], _SOURCE_KEYS, f"actions[{index}].source")
        if _safe_path(source["path"], "source.path") != chapter_path:
            raise BrokerError("action source must be the declared chapter")
        start_line = source["start_line"]
        end_line = source["end_line"]
        if (
            type(start_line) is not int
            or type(end_line) is not int
            or start_line < 1
            or end_line < start_line
            or end_line > len(chapter_lines)
        ):
            raise BrokerError(f"invalid source span for action: {action_id}")
        excerpt = "".join(chapter_lines[start_line - 1 : end_line]).encode("utf-8")
        if _sha256(excerpt) != _digest(source["sha256"], "source.sha256"):
            raise BrokerError(f"source span hash mismatch for action: {action_id}")
        expected_source = (
            f"G6_ACTION: {action_id} {operation_id}\n"
            f"{PROBE_OPERATIONS[operation_id].source_text}"
        ).encode("utf-8")
        if excerpt != expected_source:
            raise BrokerError(f"source span does not contain the exact operation: {action_id}")
        validated_actions.append(action)
    return chapter_bytes, start_files, validated_actions


def _ensure_empty_workspace(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise BrokerError("workspace must be an existing non-symlink directory")
    if any(path.iterdir()):
        raise BrokerError("workspace must be empty")


def _safe_workspace_target(workspace: Path, relative: str) -> Path:
    _safe_path(relative, "operation path")
    current = workspace
    parts = PurePosixPath(relative).parts
    for part in parts[:-1]:
        current = current / part
        if current.exists() and (current.is_symlink() or not current.is_dir()):
            raise BrokerError(f"unsafe workspace parent: {relative}")
    target = workspace.joinpath(*parts)
    if target.is_symlink():
        raise BrokerError(f"workspace symlink is forbidden: {relative}")
    return target


def _bwrap_prefix(bwrap: Path, workspace: Path, private_home: Path) -> list[str]:
    required_dirs = (
        Path("/usr/bin"),
        Path("/usr/lib"),
        Path("/lib/x86_64-linux-gnu"),
    )
    loader = Path("/lib64/ld-linux-x86-64.so.2")
    if any(not path.is_dir() for path in required_dirs) or not loader.is_file():
        raise BrokerError("fixed read-only toolchain roots are unavailable")
    return [
        str(bwrap),
        "--die-with-parent",
        "--new-session",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-net",
        "--hostname",
        "g6",
        "--clearenv",
        "--tmpfs",
        "/",
        "--dir",
        "/usr",
        "--dir",
        "/usr/bin",
        "--ro-bind",
        "/usr/bin",
        "/usr/bin",
        "--dir",
        "/usr/lib",
        "--ro-bind",
        "/usr/lib",
        "/usr/lib",
        "--dir",
        "/lib",
        "--dir",
        "/lib/x86_64-linux-gnu",
        "--ro-bind",
        "/lib/x86_64-linux-gnu",
        "/lib/x86_64-linux-gnu",
        "--dir",
        "/lib64",
        "--ro-bind",
        "/lib64/ld-linux-x86-64.so.2",
        "/lib64/ld-linux-x86-64.so.2",
        "--proc",
        "/proc",
        "--dir",
        "/work",
        "--bind",
        str(workspace),
        "/work",
        "--dir",
        "/home",
        "--dir",
        "/home/g6",
        "--bind",
        str(private_home),
        "/home/g6",
        "--setenv",
        "PATH",
        "/usr/bin",
        "--setenv",
        "HOME",
        "/home/g6",
        "--setenv",
        "LC_ALL",
        "C.UTF-8",
        "--chdir",
        "/work",
    ]


_PROBE = r"""
import json, os, socket
from pathlib import Path

def readonly_toolchain():
    try:
        Path('/usr/bin/g6-write-test').write_text('x')
    except OSError:
        return True
    return False

def blocked_network():
    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        return sock.connect_ex(('1.1.1.1', 53)) != 0
    finally:
        sock.close()

checks = {
    'clean_environment': os.environ == {
        'HOME': '/home/g6', 'LC_ALL': 'C.UTF-8', 'PATH': '/usr/bin', 'PWD': '/work'
    },
    'host_paths_hidden': not any(Path(path).exists() for path in (
        '/bin', '/etc', '/root', '/tmp', '/mnt', '/usr/local',
        '/run/docker.sock', '/var/run/docker.sock'
    )),
    'network_blocked': blocked_network(),
    'pid_namespace': os.getpid() <= 3 and os.getppid() == 1,
    'private_home': Path.home() == Path('/home/g6') and not any(Path.home().iterdir()),
    'toolchain_read_only': readonly_toolchain(),
    'uts_namespace': socket.gethostname() == 'g6',
}
print(json.dumps(checks, sort_keys=True))
"""


def _run(
    argv: list[str], *, timeout: float = 10.0
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env={},
            close_fds=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BrokerError("sandbox process could not complete") from exc


def _preflight(prefix: list[str]) -> dict[str, bool]:
    result = _run(prefix + ["/usr/bin/python3", "-c", _PROBE])
    if result.returncode != 0:
        raise BrokerError(f"bwrap preflight failed with exit {result.returncode}")
    try:
        checks = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BrokerError("bwrap preflight returned invalid evidence") from exc
    expected = {
        "clean_environment",
        "host_paths_hidden",
        "network_blocked",
        "pid_namespace",
        "private_home",
        "toolchain_read_only",
        "uts_namespace",
    }
    if (
        not isinstance(checks, dict)
        or set(checks) != expected
        or any(value is not True for value in checks.values())
    ):
        raise BrokerError(f"bwrap preflight did not pass 7/7: {checks!r}")
    return checks


def _artifact_files(workspace: Path) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise BrokerError(f"unsupported artifact entry: {relative}")
        if stat.S_ISREG(mode):
            files.append((relative, path.read_bytes()))
    return files


def _validate_bwrap(path: Path) -> None:
    if path != Path("/usr/bin/bwrap") or path.is_symlink() or not path.is_file():
        raise BrokerError("the fixed /usr/bin/bwrap executable is required")
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        or not os.access(path, os.X_OK)
    ):
        raise BrokerError("the fixed bwrap executable has unsafe ownership or mode")
    try:
        if path.read_bytes()[:4] != b"\x7fELF":
            raise BrokerError("the fixed bwrap executable is not ELF")
    except OSError as exc:
        raise BrokerError("the fixed bwrap executable cannot be read") from exc


def execute_manifest(
    manifest_path: Path, input_root: Path, workspace: Path
) -> dict[str, Any]:
    """Execute a validated manifest and return a content-addressed trace receipt."""
    if input_root.is_symlink() or not input_root.is_dir():
        raise BrokerError("input_root must be a non-symlink directory")
    _ensure_empty_workspace(workspace)
    manifest, manifest_raw = _load_manifest(manifest_path)
    chapter_bytes, start_files, actions = _validate_manifest(manifest, input_root)
    for relative, data in start_files:
        target = _safe_workspace_target(workspace, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    bwrap = BWRAP_PATH
    _validate_bwrap(bwrap)
    private_home = workspace.parent / f".{workspace.name}-g6-home"
    if private_home.exists() or private_home.is_symlink():
        raise BrokerError("private HOME path already exists")
    private_home.mkdir(mode=0o700)
    try:
        prefix = _bwrap_prefix(bwrap, workspace, private_home)
        preflight = _preflight(prefix)
        action_trace: list[dict[str, Any]] = []
        for action in actions:
            operation_id = action["operation"]
            operation = PROBE_OPERATIONS[operation_id]
            record: dict[str, Any] = {
                "id": action["id"],
                "operation": operation_id,
                "kind": operation.kind,
            }
            if operation.kind == "mkdir":
                assert operation.path is not None
                target = _safe_workspace_target(workspace, operation.path)
                target.mkdir(parents=True, exist_ok=True)
            elif operation.kind == "write":
                assert operation.path is not None and operation.content is not None
                target = _safe_workspace_target(workspace, operation.path)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and not target.is_file():
                    raise BrokerError(f"write target is not a regular file: {operation.path}")
                target.write_bytes(operation.content)
                record["content_sha256"] = _sha256(operation.content)
            elif operation.kind == "command":
                if not operation.argv or any(not arg for arg in operation.argv):
                    raise BrokerError(f"fixed command is empty: {operation_id}")
                result = _run(prefix + list(operation.argv))
                record.update(
                    {
                        "argv_sha256": _sha256(_canonical(list(operation.argv))),
                        "exit_code": result.returncode,
                        "stdout_sha256": _sha256(result.stdout.encode("utf-8")),
                        "stderr_sha256": _sha256(result.stderr.encode("utf-8")),
                    }
                )
                if result.returncode != 0:
                    raise BrokerError(
                        f"fixed command failed: {operation_id}: {result.returncode}"
                    )
            else:
                raise BrokerError(f"unsupported fixed operation kind: {operation.kind}")
            action_trace.append(record)
        artifact_files = _artifact_files(workspace)
        trace = {
            "schema": "g6-broker-trace-v1",
            "scope": "G6_BROKER_PROBE_COMPONENT_NON_FORMAL",
            "claims": {
                "formal_g6_exec": False,
                "knowledge_isolation": False,
                "ui_validated": False,
            },
            "artifact_id": manifest["artifact_id"],
            "manifest_sha256": _sha256(manifest_raw),
            "chapter_sha256": _sha256(chapter_bytes),
            "start_snapshot_sha256": snapshot_digest(start_files),
            "artifact_snapshot_sha256": snapshot_digest(artifact_files),
            "broker_source_sha256": _sha256(Path(__file__).read_bytes()),
            "probe_source_sha256": _sha256(_PROBE.encode("utf-8")),
            "operation_table_sha256": _operation_table_digest(),
            "bwrap_sha256": _sha256(bwrap.read_bytes()),
            "kernel_release_sha256": _sha256(os.uname().release.encode("utf-8")),
            "sandbox_recipe_sha256": _sha256(_canonical(prefix)),
            "preflight": preflight,
            "actions": action_trace,
        }
        return {"trace": trace, "trace_sha256": _sha256(_canonical(trace))}
    finally:
        try:
            private_home.rmdir()
        except OSError:
            # Fail closed on the next run if the supposedly private HOME was altered.
            pass
