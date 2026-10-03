#!/usr/bin/env python3
"""Fixed, isolated TypeScript check for the reviewed D4 SDK57 application.

This checks compiler acceptance only. It does not run project source, package
scripts, a model, Metro, a UI, a network service, or an independent lesson.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import resource
import signal
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from g6_broker import BWRAP_PATH, _bwrap_prefix, _preflight, _validate_bwrap, snapshot_digest


PROFILE_ID = "d4-sdk57"
MAX_TIMEOUT_SECONDS = 60.0
MAX_FILES = 256
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 96 * 1024 * 1024
MAX_DIAGNOSTIC_BYTES = 64 * 1024
SOURCE_FILES = (
    "App.tsx",
    "index.ts",
    "lib/auth-return.d.ts",
    "lib/auth-return.mjs",
    "lib/supabase.ts",
)
OPTIONAL_SOURCE = "components/RlsTrial.tsx"
TSC_RELATIVE = "typescript/bin/tsc"
PROFILE_ANCHORS = MappingProxyType({
    "typescript/package.json": "9332e97c30d3e53ed54910b89207ed657fb444066484df6e5b6965bf130865e9",
    "typescript/bin/tsc": "8d5fa5bd883fec0979fc2004f1fe1d99aef40570155d550eadc0b03b55513bf0",
    "typescript/lib/tsc.js": "2cffde0b8c6760dfb0b5b0382bbb7e00ba6a8b2d981b9205b256a700a481d983",
    "expo/package.json": "63ea81b16dee53308f73a0b43bfa945570edd4bf81d97fcdb7e549bf55a6d115",
    "react/package.json": "c383aced6a67c8d06f02996015c0a163e78532a330a96dff1ccfd107b00ab326",
    "react-native/package.json": "74d52b09a17cb0659745206323bb7cb21b6453be3ef1806054791ff3f0428ac1",
    "@supabase/supabase-js/package.json": "02e42e8011329ed38c1f774fc7b3c0b9329a93a26d39deb79e5ad31ffccb16d8",
})
_DIAGNOSTIC = re.compile(r"^(?:/|\.\./)app/([^:(]+)\((\d+),(\d+)\): (?:error|warning) (TS\d+): (.*)$")
_TS_SOURCE = re.compile(r"(?:^|/).+\.(?:d\.ts|ts|tsx)$")


class D4TypecheckError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Diagnostic:
    source: str
    line: int
    column: int
    code: str
    message_sha256: str


@dataclass(frozen=True, slots=True)
class TypecheckReceipt:
    scope: str
    profile_id: str
    passed: bool
    exit_code: int
    diagnostics: tuple[Diagnostic, ...]
    diagnostics_truncated: bool
    source_snapshot_sha256: str
    toolchain_sha256: str
    isolation_checks: tuple[str, ...]
    model_or_ui_run: bool


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path, maximum: int = 256 * 1024 * 1024) -> str:
    try:
        details = path.lstat()
    except OSError as exc:
        raise D4TypecheckError("toolchain_file_unavailable") from exc
    if not stat.S_ISREG(details.st_mode) or details.st_size > maximum:
        raise D4TypecheckError("toolchain_file_rejected")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise D4TypecheckError("toolchain_file_unavailable") from exc
    return digest.hexdigest()


def _regular(path: Path, label: str) -> bytes:
    try:
        details = path.lstat()
    except OSError as exc:
        raise D4TypecheckError(f"{label}_unavailable") from exc
    if not stat.S_ISREG(details.st_mode):
        raise D4TypecheckError(f"{label}_rejected")
    if details.st_size > MAX_FILE_BYTES:
        raise D4TypecheckError(f"{label}_too_large")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise D4TypecheckError(f"{label}_unavailable") from exc


def _snapshot(root: Path) -> tuple[str, tuple[str, ...]]:
    if root.is_symlink() or not root.is_dir():
        raise D4TypecheckError("app_root_rejected")
    files: list[tuple[str, bytes]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise D4TypecheckError("app_symlink_rejected")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".env") or "/.env" in relative:
            raise D4TypecheckError("private_environment_file_rejected")
        content = _regular(path, "app_file")
        total += len(content)
        if len(files) >= MAX_FILES or total > MAX_SNAPSHOT_BYTES:
            raise D4TypecheckError("app_snapshot_too_large")
        files.append((relative, content))
    names = tuple(path for path, _ in files)
    allowed_ts = set(SOURCE_FILES) | {OPTIONAL_SOURCE}
    if any(_TS_SOURCE.search(name) and name not in allowed_ts for name in names):
        raise D4TypecheckError("unexpected_typescript_source")
    if any(name not in names for name in SOURCE_FILES):
        raise D4TypecheckError("required_source_missing")
    return snapshot_digest(files), names


def _dependency_roots(overlay: Path, permitted: tuple[Path, ...]) -> tuple[Path, ...]:
    if overlay.is_symlink() or not overlay.is_dir() or overlay.name != "node_modules":
        raise D4TypecheckError("dependencies_root_rejected")
    try:
        permitted_real = tuple(path.resolve(strict=True) for path in permitted)
    except OSError as exc:
        raise D4TypecheckError("dependency_target_rejected") from exc
    if any(original.is_symlink() or original != resolved for original, resolved in zip(permitted, permitted_real)):
        raise D4TypecheckError("dependency_target_rejected")
    if not permitted_real or any(path.name != "node_modules" or not path.is_dir() for path in permitted_real):
        raise D4TypecheckError("dependency_target_rejected")
    seen: set[Path] = set()
    for path in overlay.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            target = path.resolve(strict=True)
        except OSError as exc:
            raise D4TypecheckError("dependency_symlink_rejected") from exc
        owners = [root for root in permitted_real if target == root or target.is_relative_to(root)]
        if len(owners) != 1:
            raise D4TypecheckError("dependency_symlink_rejected")
        seen.add(owners[0])
    if seen != set(permitted_real):
        raise D4TypecheckError("dependency_target_unused")
    for root in permitted_real:
        for path in root.rglob("*"):
            if path.is_symlink():
                target = path.resolve(strict=True)
                if target != root and not target.is_relative_to(root):
                    raise D4TypecheckError("dependency_target_symlink_rejected")
    return permitted_real


def _profile_digest(overlay: Path) -> str:
    records = []
    for relative, expected in PROFILE_ANCHORS.items():
        content = _regular(overlay / PurePosixPath(relative), "profile_anchor")
        actual = _sha256(content)
        if actual != expected:
            raise D4TypecheckError("profile_anchor_changed")
        records.append((relative, content))
    return snapshot_digest(records)


def _mount_parents(paths: tuple[Path, ...]) -> list[str]:
    existing = {"/home", "/home/g6", "/usr", "/usr/bin", "/usr/lib", "/lib", "/lib64", "/work"}
    result: list[str] = []
    for path in paths:
        current = Path("/")
        for part in path.parent.parts[1:]:
            current /= part
            value = current.as_posix()
            if value not in existing:
                result += ["--dir", value]
                existing.add(value)
    return result


def _limits(timeout: float) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (math.ceil(timeout) + 1, math.ceil(timeout) + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))


class FixedD4Typecheck:
    def __init__(
        self,
        app_root: Path,
        dependencies_root: Path,
        *,
        node_executable: Path,
        dependency_targets: tuple[Path, ...],
        timeout_seconds: float = MAX_TIMEOUT_SECONDS,
    ) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise D4TypecheckError("invalid_timeout")
        self.timeout = float(timeout_seconds)
        if not 0 < self.timeout <= MAX_TIMEOUT_SECONDS:
            raise D4TypecheckError("invalid_timeout")
        self.app_root = app_root
        self.dependencies_root = dependencies_root
        try:
            self.node = node_executable.resolve(strict=True)
        except OSError as exc:
            raise D4TypecheckError("node_executable_rejected") from exc
        if node_executable.is_symlink() or not self.node.is_file() or not os.access(self.node, os.X_OK):
            raise D4TypecheckError("node_executable_rejected")
        self.dependency_targets = dependency_targets

    def _diagnostics(self, raw: bytes) -> tuple[tuple[Diagnostic, ...], bool]:
        truncated = len(raw) > MAX_DIAGNOSTIC_BYTES
        text = raw[:MAX_DIAGNOSTIC_BYTES].decode("utf-8", errors="replace")
        output: list[Diagnostic] = []
        for line in text.splitlines():
            if not line:
                continue
            match = _DIAGNOSTIC.fullmatch(line)
            if match and match.group(1) in set(SOURCE_FILES) | {OPTIONAL_SOURCE}:
                source, row, column, code, message = match.groups()
            else:
                source, row, column = "compiler", "0", "0"
                found = re.search(r"TS\d+", line)
                code = found.group(0) if found else "TYPECHECK"
                message = line
            output.append(Diagnostic(source, int(row), int(column), code, _sha256(message.encode())))
            if len(output) == 50:
                truncated = truncated or len(text.splitlines()) > 50
                break
        return tuple(output), truncated

    def run(self, profile_id: str) -> TypecheckReceipt:
        if profile_id != PROFILE_ID:
            raise D4TypecheckError("unknown_profile")
        before, names = _snapshot(self.app_root)
        targets = _dependency_roots(self.dependencies_root, self.dependency_targets)
        toolchain_sha = _profile_digest(self.dependencies_root)
        node_sha = _file_sha256(self.node)
        toolchain_sha = _sha256(f"{toolchain_sha}:{node_sha}".encode())
        _validate_bwrap(BWRAP_PATH)

        with tempfile.TemporaryDirectory(prefix="d4-typecheck-") as temporary:
            root = Path(temporary)
            work = root / "work"
            home = root / "home"
            work.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            files = [name for name in SOURCE_FILES if name.endswith((".ts", ".tsx"))]
            if OPTIONAL_SOURCE in names:
                files.append(OPTIONAL_SOURCE)
            config = {
                "compilerOptions": {
                    "allowJs": True, "checkJs": False, "customConditions": ["react-native"], "esModuleInterop": True,
                    "incremental": False, "jsx": "react-jsx", "lib": ["DOM", "ESNext"],
                    "module": "preserve", "moduleDetection": "force", "moduleResolution": "bundler",
                    "noEmit": True, "resolveJsonModule": True, "skipLibCheck": True,
                    "strict": True, "target": "ESNext",
                },
                "files": [f"/app/{name}" for name in files],
            }
            config_path = work / "tsconfig.json"
            config_path.write_text(json.dumps(config, sort_keys=True, separators=(",", ":")))
            config_path.chmod(0o600)
            app_mount = root / "app"
            for directory in (app_mount, app_mount / "lib", app_mount / "components", app_mount / "node_modules"):
                directory.mkdir(mode=0o700)
            for name in SOURCE_FILES + ((OPTIONAL_SOURCE,) if OPTIONAL_SOURCE in names else ()):
                target = app_mount / name
                target.parent.mkdir(mode=0o700, exist_ok=True)
                target.touch(mode=0o600)
            prefix = _bwrap_prefix(BWRAP_PATH, work, home)
            checks = _preflight(prefix)
            mounts = ["--dir", "/toolchain", "--ro-bind", str(self.node), "/toolchain/node", "--dir", "/app", "--ro-bind", str(app_mount), "/app"]
            for name in SOURCE_FILES + ((OPTIONAL_SOURCE,) if OPTIONAL_SOURCE in names else ()):
                mounts += ["--ro-bind", str(self.app_root / name), f"/app/{name}"]
            mounts += ["--ro-bind", str(self.dependencies_root), "/app/node_modules"]
            mounts += _mount_parents(targets)
            for target in targets:
                mounts += ["--ro-bind", str(target), target.as_posix()]
            probe = "import pathlib;\nfor p in ('/app/.write','/app/node_modules/.write'):\n\n try:pathlib.Path(p).write_text('x');raise SystemExit(9)\n except OSError:pass"
            probe_result = subprocess.run(prefix + mounts + ["/usr/bin/python3", "-c", probe], env={}, capture_output=True, timeout=10, check=False)
            if probe_result.returncode != 0:
                raise D4TypecheckError("readonly_mount_probe_failed")
            stdout_path, stderr_path = root / "stdout", root / "stderr"
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                process = subprocess.Popen(
                    prefix + mounts + ["/toolchain/node", "/app/node_modules/typescript/bin/tsc", "--project", "/work/tsconfig.json", "--pretty", "false"],
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, env={}, close_fds=True,
                    shell=False, start_new_session=True, preexec_fn=lambda: _limits(self.timeout),
                )
                try:
                    exit_code = process.wait(timeout=self.timeout)
                except subprocess.TimeoutExpired as exc:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise D4TypecheckError("typecheck_timeout") from exc
            raw = stdout_path.read_bytes() + b"\n" + stderr_path.read_bytes()
        after, _ = _snapshot(self.app_root)
        if after != before:
            raise D4TypecheckError("app_source_changed")
        diagnostics, truncated = self._diagnostics(raw)
        return TypecheckReceipt(
            scope="D4_ISOLATED_TYPECHECK_NOT_INDEPENDENT_EXEC", profile_id=PROFILE_ID,
            passed=exit_code == 0, exit_code=exit_code, diagnostics=diagnostics,
            diagnostics_truncated=truncated, source_snapshot_sha256=before,
            toolchain_sha256=toolchain_sha,
            isolation_checks=tuple(sorted((*checks, "app_read_only", "dependencies_read_only"))),
            model_or_ui_run=False,
        )
