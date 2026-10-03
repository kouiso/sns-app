#!/usr/bin/env python3
"""Process-held lease for one dedicated D4 provider/UI resource.

This is a trusted-controller coordination primitive. It does not contact WDA,
the database, Auth, or the network, and cannot constrain noncooperative clients.
Dispatch checks the deadline before and after calling an operation. It cannot
cancel an operation already in flight, so an expired operation may already have
side effects even though dispatch refuses to return success. Holding the lease
is not evidence of formal A5 or any other acceptance gate.
"""
from __future__ import annotations

import fcntl
import json
import os
import pwd
import re
import stat
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar


LOCK_DIRECTORY_NAME = "sns-d4-ui-controller"
LOCK_FILE_NAME = "provider-ui.lock"
MAX_LEASE_SECONDS = 3600.0
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{16,64}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_T = TypeVar("_T")
_ACTIVE_DESCRIPTORS: set[int] = set()
_FORK_GUARD = threading.Lock()


def _close_inherited_descriptors() -> None:
    """Drop fork-inherited references without unlocking the shared description."""
    for descriptor in tuple(_ACTIVE_DESCRIPTORS):
        try:
            os.close(descriptor)
        except OSError:
            pass
    _ACTIVE_DESCRIPTORS.clear()
    _FORK_GUARD.release()


def _prepare_for_fork() -> None:
    _FORK_GUARD.acquire()


def _resume_after_fork() -> None:
    _FORK_GUARD.release()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_prepare_for_fork,
        after_in_parent=_resume_after_fork,
        after_in_child=_close_inherited_descriptors,
    )


class LeaseError(Exception):
    """Expected fail-closed lease rejection with a fixed code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def persistent_lock_directory() -> Path:
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, TypeError) as exc:
        raise LeaseError("persistent_home_rejected") from exc
    if not home.is_absolute():
        raise LeaseError("persistent_home_rejected")
    return home / ".local" / "state" / LOCK_DIRECTORY_NAME


def _validate_directory(path: Path, *, private: bool) -> None:
    try:
        details = path.lstat()
    except OSError as exc:
        raise LeaseError("lease_directory_rejected") from exc
    if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid():
        raise LeaseError("lease_directory_rejected")
    if private and stat.S_IMODE(details.st_mode) != 0o700:
        raise LeaseError("lease_directory_rejected")


def _create_directory(path: Path, *, private: bool) -> None:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    except OSError as exc:
        raise LeaseError("lease_directory_rejected") from exc
    _validate_directory(path, private=private)


def ensure_lock_directory(test_directory: Path | None = None) -> Path:
    if test_directory is not None:
        _create_directory(test_directory, private=True)
        return test_directory
    directory = persistent_lock_directory()
    home = directory.parent.parent.parent
    _validate_directory(home, private=False)
    _create_directory(home / ".local", private=False)
    _create_directory(home / ".local" / "state", private=False)
    _create_directory(directory, private=True)
    return directory


def _validate_hex(value: Any, pattern: re.Pattern[str], code: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise LeaseError(code)
    return value


class D4UILease:
    """One-shot, process-bound lease for the fixed provider/UI resource."""

    def __init__(
        self,
        *,
        run_id: str,
        resource_fingerprint: str,
        chapter_sha256: str,
        start_sha256: str,
        lease_seconds: float,
        _test_directory: Path | None = None,
    ) -> None:
        self._binding = {
            "run_id": _validate_hex(run_id, RUN_ID_PATTERN, "invalid_run_id"),
            "resource_fingerprint": _validate_hex(
                resource_fingerprint, SHA256_PATTERN, "invalid_resource_fingerprint"
            ),
            "chapter_sha256": _validate_hex(chapter_sha256, SHA256_PATTERN, "invalid_chapter_sha256"),
            "start_sha256": _validate_hex(start_sha256, SHA256_PATTERN, "invalid_start_sha256"),
        }
        self._lease_seconds = self._validate_duration(lease_seconds)
        self._test_directory = _test_directory
        self._state = "new"
        self._descriptor: int | None = None
        self._owner_pid: int | None = None
        self._deadline: float | None = None

    @staticmethod
    def _validate_duration(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LeaseError("invalid_lease_duration")
        duration = float(value)
        if not 0.0 < duration <= MAX_LEASE_SECONDS:
            raise LeaseError("invalid_lease_duration")
        return duration

    def _lock_path(self) -> Path:
        return ensure_lock_directory(self._test_directory) / LOCK_FILE_NAME

    def _metadata(self) -> bytes:
        if self._deadline is None or self._owner_pid is None:
            raise LeaseError("lease_not_active")
        document = {
            **self._binding,
            "deadline_monotonic": self._deadline,
            "owner_pid": self._owner_pid,
        }
        return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()

    def _write_metadata(self) -> None:
        if self._descriptor is None:
            raise LeaseError("lease_not_active")
        encoded = self._metadata()
        try:
            os.lseek(self._descriptor, 0, os.SEEK_SET)
            os.ftruncate(self._descriptor, 0)
            offset = 0
            while offset < len(encoded):
                written = os.write(self._descriptor, encoded[offset:])
                if written <= 0:
                    raise OSError("short lease metadata write")
                offset += written
            os.fsync(self._descriptor)
        except OSError as exc:
            raise LeaseError("lease_metadata_rejected") from exc

    def acquire(self) -> "D4UILease":
        if self._state != "new":
            raise LeaseError("lease_reused")
        self._state = "failed"
        path = self._lock_path()
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor: int | None = None
        try:
            with _FORK_GUARD:
                try:
                    descriptor = os.open(path, flags, 0o600)
                except OSError as exc:
                    raise LeaseError("lease_file_rejected") from exc
                os.set_inheritable(descriptor, False)
                details = os.fstat(descriptor)
                path_details = path.lstat()
                if (
                    not stat.S_ISREG(details.st_mode)
                    or details.st_uid != os.getuid()
                    or stat.S_IMODE(details.st_mode) != 0o600
                    or (details.st_dev, details.st_ino) != (path_details.st_dev, path_details.st_ino)
                ):
                    raise LeaseError("lease_file_rejected")
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise LeaseError("lease_unavailable") from exc
                _ACTIVE_DESCRIPTORS.add(descriptor)
            self._descriptor = descriptor
            self._owner_pid = os.getpid()
            self._deadline = time.monotonic() + self._lease_seconds
            self._state = "active"
            self._write_metadata()
            return self
        except Exception:
            self._state = "failed"
            if descriptor is not None:
                with _FORK_GUARD:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                    except OSError:
                        pass
                    try:
                        os.close(descriptor)
                    finally:
                        _ACTIVE_DESCRIPTORS.discard(descriptor)
                self._descriptor = None
            raise

    def _validate_binding(
        self,
        *,
        run_id: str,
        resource_fingerprint: str,
        chapter_sha256: str,
        start_sha256: str,
    ) -> None:
        supplied = {
            "run_id": run_id,
            "resource_fingerprint": resource_fingerprint,
            "chapter_sha256": chapter_sha256,
            "start_sha256": start_sha256,
        }
        if supplied != self._binding:
            raise LeaseError("foreign_lease_binding")

    def check(self, **binding: str) -> float:
        if self._state == "expired":
            raise LeaseError("lease_expired")
        if self._state != "active" or self._descriptor is None:
            raise LeaseError("lease_not_active")
        if self._owner_pid != os.getpid():
            raise LeaseError("foreign_lease_process")
        self._validate_binding(**binding)
        assert self._deadline is not None
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            self._state = "expired"
            raise LeaseError("lease_expired")
        return remaining

    def renew(self, lease_seconds: float, **binding: str) -> float:
        self.check(**binding)
        new_duration = self._validate_duration(lease_seconds)
        self._lease_seconds = new_duration
        self._deadline = time.monotonic() + self._lease_seconds
        try:
            self._write_metadata()
        except Exception:
            self._state = "expired"
            raise
        return self.check(**binding)

    def dispatch(self, operation: Callable[..., _T], *args: Any, binding: dict[str, str], **kwargs: Any) -> _T:
        if not callable(operation):
            raise LeaseError("invalid_dispatch_operation")
        checked_binding = dict(binding)
        self.check(**checked_binding)
        result = operation(*args, **kwargs)
        self.check(**checked_binding)
        return result

    def release(self) -> None:
        if self._state not in {"active", "expired"} or self._descriptor is None:
            raise LeaseError("lease_not_active")
        if self._owner_pid != os.getpid():
            raise LeaseError("foreign_lease_process")
        descriptor = self._descriptor
        self._descriptor = None
        self._state = "released"
        self._deadline = None
        try:
            os.ftruncate(descriptor, 0)
            os.fsync(descriptor)
        finally:
            with _FORK_GUARD:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    try:
                        os.close(descriptor)
                    finally:
                        _ACTIVE_DESCRIPTORS.discard(descriptor)

    def __enter__(self) -> "D4UILease":
        return self.acquire()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._state in {"active", "expired"}:
            self.release()
