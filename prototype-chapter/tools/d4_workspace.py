"""Bounded read/edit capability for the non-formal D4 chapter workspace.

The capability copies the pinned starter and chapter into a new local workspace.
It exposes source text and two model-owned outputs only.  It does not run commands,
read environment variables, contact providers, or reconstruct the chapter's answer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import Any


FROZEN_MANIFEST_SHA256 = "47d8688cf92e003efbff7e032280b4f1b9827911307ddf4c9c6c4ee52ad20ab4"
FROZEN_CHAPTER_SHA256 = "93145b45bf929d867bbcee35b022d83e521510f9b54c4f31f0400f24fa340d37"
FROZEN_START_SNAPSHOT_SHA256 = "9d6d508750d8341faf5a3ac7cd05434ba1c181ef127d8dbfa932b3e28fff99d5"
MAX_CONTENT_BYTES = 128 * 1024
MAX_REQUEST_BYTES = 256 * 1024
MAX_FILE_BYTES = 1024 * 1024

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_START_PATHS = frozenset(
    {
        ".gitignore",
        "App.tsx",
        "LICENSE",
        "README.md",
        "app.json",
        "assets/android-icon-background.png",
        "assets/android-icon-foreground.png",
        "assets/android-icon-monochrome.png",
        "assets/favicon.png",
        "assets/icon.png",
        "assets/splash-icon.png",
        "index.ts",
        "lib/auth-return.d.ts",
        "lib/auth-return.mjs",
        "lib/supabase.ts",
        "package-lock.json",
        "package.json",
        "test-auth-return.mjs",
        "tsconfig.json",
    }
)
_START_DIRECTORIES = frozenset({"assets", "lib"})
_START_SIZES = {
    ".gitignore": 447,
    "App.tsx": 22366,
    "LICENSE": 1106,
    "README.md": 4602,
    "app.json": 747,
    "assets/android-icon-background.png": 17549,
    "assets/android-icon-foreground.png": 78796,
    "assets/android-icon-monochrome.png": 4140,
    "assets/favicon.png": 1129,
    "assets/icon.png": 393493,
    "assets/splash-icon.png": 17547,
    "index.ts": 307,
    "lib/auth-return.d.ts": 1458,
    "lib/auth-return.mjs": 6974,
    "lib/supabase.ts": 4319,
    "package-lock.json": 244092,
    "package.json": 755,
    "test-auth-return.mjs": 12147,
    "tsconfig.json": 85,
}
_MANIFEST_SIZE = 2882
_CHAPTER_SIZE = 20557
_COMPONENT_PATH = "app/components/RlsTrial.tsx"
_APP_PATH = "app/App.tsx"
_CHAPTER_PATH = "chapter.md"
_EDITABLE_PATHS = frozenset({_APP_PATH, _COMPONENT_PATH})


class WorkspaceError(ValueError):
    """Fixed public rejection without a host filesystem path."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _snapshot_digest(files: list[tuple[str, bytes]]) -> str:
    records = [{"path": path, "sha256": _sha256(data)} for path, data in files]
    return _sha256(_canonical(records))


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise WorkspaceError("invalid_path")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise WorkspaceError("invalid_path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise WorkspaceError("invalid_path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise WorkspaceError("invalid_path")
    return value


def _scan_tree(root: Path) -> tuple[set[str], set[str]]:
    try:
        details = root.lstat()
    except OSError as exc:
        raise WorkspaceError("workspace_tampered") from exc
    if not stat.S_ISDIR(details.st_mode) or stat.S_ISLNK(details.st_mode):
        raise WorkspaceError("workspace_tampered")
    files: set[str] = set()
    directories: set[str] = set()
    pending = [(root, "")]
    try:
        while pending:
            directory, prefix = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    relative = f"{prefix}/{entry.name}" if prefix else entry.name
                    node = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(node.st_mode):
                        raise WorkspaceError("workspace_tampered")
                    if stat.S_ISDIR(node.st_mode):
                        directories.add(relative)
                        pending.append((Path(entry.path), relative))
                    elif stat.S_ISREG(node.st_mode):
                        files.add(relative)
                    else:
                        raise WorkspaceError("workspace_tampered")
    except WorkspaceError:
        raise
    except OSError as exc:
        raise WorkspaceError("workspace_tampered") from exc
    return files, directories


def _read_regular(path: Path, error_code: str, maximum: int = MAX_FILE_BYTES) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode) or details.st_size > maximum:
                raise WorkspaceError(error_code)
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
                if not chunk:
                    return b"".join(chunks)
                total += len(chunk)
                if total > maximum:
                    raise WorkspaceError(error_code)
                chunks.append(chunk)
        finally:
            os.close(descriptor)
    except WorkspaceError:
        raise
    except OSError as exc:
        raise WorkspaceError(error_code) from exc


def _request_size(arguments: object) -> int:
    try:
        encoded = _canonical(arguments)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise WorkspaceError("invalid_arguments") from exc
    if len(encoded) > MAX_REQUEST_BYTES:
        raise WorkspaceError("request_too_large")
    return len(encoded)


def _closed_arguments(arguments: object, fields: frozenset[str]) -> dict[str, Any]:
    _request_size(arguments)
    if not isinstance(arguments, dict) or set(arguments) != fields:
        raise WorkspaceError("invalid_arguments")
    return arguments


def _source_text(value: object) -> tuple[str, bytes]:
    if not isinstance(value, str):
        raise WorkspaceError("invalid_content")
    if any(
        (ord(character) < 32 and character not in "\t\n") or ord(character) == 127
        for character in value
    ):
        raise WorkspaceError("invalid_content")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise WorkspaceError("invalid_content") from exc
    if len(encoded) > MAX_CONTENT_BYTES:
        raise WorkspaceError("content_too_large")
    return value, encoded


def _source_bytes(value: bytes) -> str:
    if len(value) > MAX_CONTENT_BYTES:
        raise WorkspaceError("content_too_large")
    try:
        text = value.decode("utf-8")
    except UnicodeError as exc:
        raise WorkspaceError("invalid_content") from exc
    _source_text(text)
    return text


class D4Workspace:
    """One controller-owned D4 source workspace."""

    def __init__(
        self,
        workspace_root: Path,
        start_hashes: dict[str, str],
        authorized_outputs: dict[str, str | None] | None = None,
    ) -> None:
        self._root = workspace_root
        self._start_hashes = dict(start_hashes)
        self._lock = threading.RLock()
        self._public_paths = frozenset(
            {_CHAPTER_PATH, _COMPONENT_PATH}
            | {f"app/{path}" for path in _START_PATHS}
        )
        if authorized_outputs is None:
            self._authorized_outputs: dict[str, str | None] = {
                _APP_PATH: self._start_hashes.get("App.tsx"),
                _COMPONENT_PATH: None,
            }
        else:
            if not isinstance(authorized_outputs, dict) or set(authorized_outputs) != _EDITABLE_PATHS:
                raise WorkspaceError("authorized_outputs_rejected")
            app_digest = authorized_outputs[_APP_PATH]
            component_digest = authorized_outputs[_COMPONENT_PATH]
            if not isinstance(app_digest, str) or _SHA256.fullmatch(app_digest) is None:
                raise WorkspaceError("authorized_outputs_rejected")
            if component_digest is not None and (
                not isinstance(component_digest, str) or _SHA256.fullmatch(component_digest) is None
            ):
                raise WorkspaceError("authorized_outputs_rejected")
            self._authorized_outputs = dict(authorized_outputs)
        if not isinstance(self._authorized_outputs[_APP_PATH], str):
            raise WorkspaceError("authorized_outputs_rejected")
        self._verify_workspace()

    @classmethod
    def create(cls, candidate_root: Path, workspace_root: Path) -> "D4Workspace":
        """Copy the pinned starter and chapter into a new workspace."""

        candidate = Path(candidate_root)
        workspace = Path(workspace_root)
        try:
            if workspace.exists() or workspace.is_symlink():
                raise WorkspaceError("workspace_exists")
            candidate_absolute = candidate.absolute()
            workspace_absolute = workspace.absolute()
            if candidate_absolute == workspace_absolute or candidate_absolute in workspace_absolute.parents:
                raise WorkspaceError("workspace_location_rejected")
            parent = workspace.parent
            parent_details = parent.lstat()
            if not stat.S_ISDIR(parent_details.st_mode) or stat.S_ISLNK(parent_details.st_mode):
                raise WorkspaceError("workspace_location_rejected")

            manifest_bytes = _read_regular(
                candidate / "start-manifest.json", "candidate_rejected", maximum=_MANIFEST_SIZE
            )
            if _sha256(manifest_bytes) != FROZEN_MANIFEST_SHA256:
                raise WorkspaceError("candidate_rejected")
            try:
                manifest = json.loads(manifest_bytes)
            except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
                raise WorkspaceError("candidate_rejected") from exc
            entries = manifest.get("files") if isinstance(manifest, dict) else None
            if not isinstance(entries, list) or len(entries) != 19:
                raise WorkspaceError("candidate_rejected")
            start_hashes: dict[str, str] = {}
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
                    raise WorkspaceError("candidate_rejected")
                path = _safe_relative(entry["path"])
                digest = entry["sha256"]
                if path in start_hashes or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                    raise WorkspaceError("candidate_rejected")
                start_hashes[path] = digest
            if set(start_hashes) != _START_PATHS:
                raise WorkspaceError("candidate_rejected")

            start_root = candidate / "start"
            files, directories = _scan_tree(start_root)
            if files != _START_PATHS or directories != _START_DIRECTORIES:
                raise WorkspaceError("candidate_rejected")
            start_data: dict[str, bytes] = {}
            for relative, digest in start_hashes.items():
                data = _read_regular(
                    start_root / relative,
                    "candidate_rejected",
                    maximum=_START_SIZES[relative],
                )
                if _sha256(data) != digest:
                    raise WorkspaceError("candidate_rejected")
                start_data[relative] = data
            if _snapshot_digest(sorted(start_data.items())) != FROZEN_START_SNAPSHOT_SHA256:
                raise WorkspaceError("candidate_rejected")

            chapter = _read_regular(
                candidate / "chapter-build.md", "candidate_rejected", maximum=_CHAPTER_SIZE
            )
            if _sha256(chapter) != FROZEN_CHAPTER_SHA256:
                raise WorkspaceError("candidate_rejected")
            try:
                chapter.decode("utf-8")
            except UnicodeError as exc:
                raise WorkspaceError("candidate_rejected") from exc

            workspace.mkdir(mode=0o700)
            try:
                app_root = workspace / "app"
                app_root.mkdir(mode=0o700)
                for relative in sorted(_START_DIRECTORIES):
                    (app_root / relative).mkdir(mode=0o700)
                for relative, data in start_data.items():
                    target = app_root / relative
                    target.write_bytes(data)
                    target.chmod(0o600 if relative == "App.tsx" else 0o400)
                chapter_target = workspace / _CHAPTER_PATH
                chapter_target.write_bytes(chapter)
                chapter_target.chmod(0o400)
            except Exception:
                shutil.rmtree(workspace, ignore_errors=True)
                raise
            instance = cls(workspace, start_hashes)
            instance.verify_inventory()
            return instance
        except WorkspaceError:
            raise
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            raise WorkspaceError("workspace_io_rejected") from exc

    def _verify_workspace(
        self, authorized_outputs: dict[str, str | None] | None = None
    ) -> dict[str, bytes]:
        authorized = self._authorized_outputs if authorized_outputs is None else authorized_outputs
        files, directories = _scan_tree(self._root)
        expected_files = {_CHAPTER_PATH} | {f"app/{path}" for path in _START_PATHS}
        if authorized[_COMPONENT_PATH] is not None:
            expected_files.add(_COMPONENT_PATH)
        expected_directories = {"app", "app/assets", "app/lib"}
        if "app/components" in directories:
            expected_directories.add("app/components")
        if files != expected_files or directories != expected_directories:
            raise WorkspaceError("workspace_tampered")

        data: dict[str, bytes] = {}
        for public_path in sorted(files):
            if public_path in _EDITABLE_PATHS:
                maximum = MAX_CONTENT_BYTES
            elif public_path == _CHAPTER_PATH:
                maximum = _CHAPTER_SIZE
            else:
                maximum = _START_SIZES[public_path.removeprefix("app/")]
            content = _read_regular(
                self._root / public_path, "workspace_tampered", maximum=maximum
            )
            data[public_path] = content
            if public_path == _CHAPTER_PATH:
                if _sha256(content) != FROZEN_CHAPTER_SHA256:
                    raise WorkspaceError("workspace_tampered")
            elif public_path.startswith("app/"):
                relative = public_path.removeprefix("app/")
                if relative in self._start_hashes and relative != "App.tsx":
                    if _sha256(content) != self._start_hashes[relative]:
                        raise WorkspaceError("workspace_tampered")
            if public_path in _EDITABLE_PATHS:
                if _sha256(content) != authorized[public_path]:
                    raise WorkspaceError("workspace_tampered")
                try:
                    _source_bytes(content)
                except WorkspaceError as exc:
                    raise WorkspaceError("workspace_tampered") from exc
        return data

    def _public_path(self, value: object) -> str:
        path = _safe_relative(value)
        if path not in self._public_paths:
            raise WorkspaceError("invalid_path")
        return path

    def read_file(self, arguments: dict[str, object]) -> dict[str, object]:
        with self._lock:
            try:
                data = self._verify_workspace()
                request = _closed_arguments(arguments, frozenset({"path"}))
                path = self._public_path(request["path"])
                if path not in data:
                    raise WorkspaceError("file_missing")
                content = data[path]
                if len(content) > MAX_CONTENT_BYTES:
                    raise WorkspaceError("content_too_large")
                try:
                    text = content.decode("utf-8")
                except UnicodeError as exc:
                    raise WorkspaceError("file_not_text") from exc
                return {
                    "path": path,
                    "sha256": _sha256(content),
                    "bytes": len(content),
                    "editable": path in _EDITABLE_PATHS,
                    "content": text,
                }
            except WorkspaceError:
                raise
            except (OSError, UnicodeError, ValueError, RecursionError) as exc:
                raise WorkspaceError("workspace_io_rejected") from exc

    def edit_file(self, arguments: dict[str, object]) -> dict[str, object]:
        with self._lock:
            try:
                data = self._verify_workspace()
                request = _closed_arguments(
                    arguments, frozenset({"path", "expected_sha256", "content"})
                )
                path = self._public_path(request["path"])
                if path not in _EDITABLE_PATHS:
                    raise WorkspaceError("readonly_path")
                _, encoded = _source_text(request["content"])
                expected = request["expected_sha256"]
                current = data.get(path)
                if current is None:
                    if path != _COMPONENT_PATH or expected is not None:
                        raise WorkspaceError("stale_cas")
                else:
                    if not isinstance(expected, str) or _SHA256.fullmatch(expected) is None:
                        raise WorkspaceError("expected_sha256_required")
                    if expected != _sha256(current):
                        raise WorkspaceError("stale_cas")

                target = self._root / path
                parent = target.parent
                if path == _COMPONENT_PATH and not parent.exists():
                    parent.mkdir(mode=0o700)
                descriptor, temporary = tempfile.mkstemp(prefix=".d4-edit-", dir=parent)
                try:
                    os.fchmod(descriptor, 0o600)
                    offset = 0
                    while offset < len(encoded):
                        written = os.write(descriptor, encoded[offset:])
                        if written <= 0:
                            raise OSError("short write")
                        offset += written
                    os.fsync(descriptor)
                    os.close(descriptor)
                    descriptor = -1
                    os.replace(temporary, target)
                    directory_descriptor = os.open(parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_descriptor)
                    finally:
                        os.close(directory_descriptor)
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                    try:
                        os.unlink(temporary)
                    except FileNotFoundError:
                        pass
                updated_outputs = dict(self._authorized_outputs)
                updated_outputs[path] = _sha256(encoded)
                self._verify_workspace(updated_outputs)
                self._authorized_outputs = updated_outputs
                return {
                    "path": path,
                    "previous_sha256": _sha256(current) if current is not None else None,
                    "sha256": _sha256(encoded),
                    "bytes": len(encoded),
                }
            except WorkspaceError:
                raise
            except (OSError, UnicodeError, ValueError, RecursionError) as exc:
                raise WorkspaceError("workspace_io_rejected") from exc

    def verify_inventory(self) -> dict[str, object]:
        with self._lock:
            try:
                data = self._verify_workspace()
                files = []
                for path, content in sorted(data.items()):
                    try:
                        content.decode("utf-8")
                        textual = True
                    except UnicodeError:
                        textual = False
                    files.append(
                        {
                            "path": path,
                            "sha256": _sha256(content),
                            "bytes": len(content),
                            "textual": textual,
                            "editable": path in _EDITABLE_PATHS,
                        }
                    )
                return {
                    "schema": "d4-workspace-inventory-v1",
                    "files": files,
                    "component_present": _COMPONENT_PATH in data,
                }
            except WorkspaceError:
                raise
            except (OSError, UnicodeError, ValueError, RecursionError) as exc:
                raise WorkspaceError("workspace_io_rejected") from exc

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            try:
                data = self._verify_workspace()
                outputs = [
                    (path, data[path])
                    for path in sorted(_EDITABLE_PATHS)
                    if path in data
                ]
                records = [
                    {"path": path, "sha256": _sha256(content), "bytes": len(content)}
                    for path, content in outputs
                ]
                return {
                    "schema": "d4-workspace-output-snapshot-v1",
                    "files": records,
                    "snapshot_sha256": _snapshot_digest(outputs),
                }
            except WorkspaceError:
                raise
            except (OSError, UnicodeError, ValueError, RecursionError) as exc:
                raise WorkspaceError("workspace_io_rejected") from exc
