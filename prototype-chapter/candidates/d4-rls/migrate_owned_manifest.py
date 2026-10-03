#!/usr/bin/env python3
"""Explicitly copy reviewed legacy owned-run metadata into persistent state.

This tool only reads the fixed dedicated database. It leaves the legacy file
unchanged and never repairs, deletes, renames, or seeds database rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import reconcile_owned
import reset_owned


LEGACY_DIRECTORY = Path("/tmp/sns-d4-owned-runs")
ALLOWED_LEGACY_SOURCE_SHA256 = frozenset({
    "2bf5cdecca51929dced9232200e8113317e0488f53b63df28ae14e279ffb020f",
})
EXPECTED_CURRENT_RESET_SHA256 = "6d01cba56da854ccb43ba747a74c1e5b70024004ec09f93f7c29a4de53c8e517"


def migration_source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def legacy_manifest_path(run_id: str, base_directory: Path | None = None) -> Path:
    return reset_owned.manifest_path(run_id, LEGACY_DIRECTORY if base_directory is None else base_directory)


def destination_paths(run_id: str, base_directory: Path | None = None) -> dict[str, Path]:
    valid = reset_owned.validate_run_id(run_id)
    base = reset_owned.persistent_manifest_directory() if base_directory is None else base_directory
    names = {
        "legacy": f"{valid}.legacy.json",
        "manifest": f"{valid}.json",
        "receipt": f"{valid}.migration.json",
    }
    paths = {label: base / name for label, name in names.items()}
    if any(path.parent != base or path.name != names[label] for label, path in paths.items()):
        raise reset_owned.OwnedRunError("invalid_manifest_path")
    return paths


def encode_json(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_or_verify_private(path: Path, content: bytes) -> bool:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        if reset_owned.read_private_bytes(path) != content:
            raise reset_owned.OwnedRunError("persistent_collision")
        return False
    try:
        offset = 0
        while offset < len(content):
            offset += os.write(descriptor, content[offset:])
        os.fsync(descriptor)
        details = os.fstat(descriptor)
        if details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != 0o600:
            raise reset_owned.OwnedRunError("manifest_mode_rejected")
    except Exception:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        reset_owned.fsync_directory(path.parent)
        raise
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
    reset_owned.fsync_directory(path.parent)
    return True


def persist_migration(
    run_id: str,
    legacy_bytes: bytes,
    current_document: dict[str, Any],
    receipt: dict[str, Any],
    *,
    base_directory: Path | None = None,
) -> int:
    paths = destination_paths(run_id, base_directory)
    created = 0
    for path, content in (
        (paths["legacy"], legacy_bytes),
        (paths["manifest"], encode_json(current_document)),
        (paths["receipt"], encode_json(receipt)),
    ):
        created += int(write_or_verify_private(path, content))
    return created


def migrate(payload: dict[str, str]) -> dict[str, Any]:
    current_reset_sha = reset_owned.source_sha256()
    if current_reset_sha != EXPECTED_CURRENT_RESET_SHA256:
        raise reset_owned.OwnedRunError("reset_source_changed")
    reset_owned._validate_owned_directory(LEGACY_DIRECTORY, private=True)
    old_path = legacy_manifest_path(payload["run_id"])
    legacy_bytes = reset_owned.read_private_bytes(old_path)
    try:
        old_document = json.loads(legacy_bytes)
    except json.JSONDecodeError as exc:
        raise reset_owned.OwnedRunError("manifest_rejected") from exc
    reset_owned.validate_manifest(old_document)
    if old_document["actors"] != {"a": payload["actor_a"], "b": payload["actor_b"]}:
        raise reset_owned.OwnedRunError("manifest_actor_mismatch")
    if old_document["source_sha256"] not in ALLOWED_LEGACY_SOURCE_SHA256:
        raise reset_owned.OwnedRunError("legacy_source_rejected")

    reset_owned.verify_dedicated_database()
    state = reconcile_owned.query_owned_state(old_document, payload["run_id"])
    if state["status"] not in {"absent", "seeded"}:
        raise reset_owned.OwnedRunError("legacy_database_state_rejected")
    if state["references"] != 0:
        raise reset_owned.OwnedRunError("legacy_references_rejected")
    reset_owned.ensure_manifest_directory()

    current_document = {
        "source_sha256": current_reset_sha,
        "actors": old_document["actors"],
        "posts": old_document["posts"],
    }
    reset_owned.validate_manifest(current_document)
    old_hash = hashlib.sha256(legacy_bytes).hexdigest()
    new_bytes = encode_json(current_document)
    new_hash = hashlib.sha256(new_bytes).hexdigest()
    receipt = {
        "database_state": state["status"],
        "legacy_manifest_sha256": old_hash,
        "legacy_source_sha256": old_document["source_sha256"],
        "migration_sha256": migration_source_sha256(),
        "persistent_manifest_sha256": new_hash,
        "reset_source_sha256": current_reset_sha,
    }
    created = persist_migration(payload["run_id"], legacy_bytes, current_document, receipt)
    return {
        "status": "migrated" if created else "verified",
        "database_state": state["status"],
        "files_created": created,
        "legacy_manifest_sha256": old_hash,
        "persistent_manifest_sha256": new_hash,
        "reset_sha256": current_reset_sha,
        "migration_sha256": receipt["migration_sha256"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        payload = reset_owned.parse_stdin_payload(sys.stdin.read(), args.run_id)
        print(json.dumps(migrate(payload), sort_keys=True, separators=(",", ":")))
        return 0
    except reset_owned.OwnedRunError as exc:
        print(json.dumps({"status": "error", "code": exc.code}, sort_keys=True, separators=(",", ":")))
        return 2
    except Exception:
        print(json.dumps({"status": "error", "code": "internal_error"}, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
