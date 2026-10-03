#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import stat
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import migrate_owned_manifest
import reset_owned


class MigrateOwnedManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = "ef" * 12
        self.actors = {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())}
        self.posts = {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())}
        self.payload = {
            "run_id": self.run_id,
            "actor_a": self.actors["a"],
            "actor_b": self.actors["b"],
        }

    def document(self, source: str) -> dict[str, object]:
        return {"source_sha256": source, "actors": self.actors, "posts": self.posts}

    @staticmethod
    def write_private(path: Path, document: dict[str, object]) -> bytes:
        raw = migrate_owned_manifest.encode_json(document)
        path.write_bytes(raw)
        path.chmod(0o600)
        return raw

    def test_unreviewed_legacy_source_is_rejected_before_database_query(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            legacy = Path(temporary)
            legacy.chmod(0o700)
            self.write_private(legacy / f"{self.run_id}.json", self.document("0" * 64))
            with (
                mock.patch.object(migrate_owned_manifest, "LEGACY_DIRECTORY", legacy),
                mock.patch.object(reset_owned, "verify_dedicated_database") as database,
            ):
                with self.assertRaisesRegex(reset_owned.OwnedRunError, "legacy_source_rejected"):
                    migrate_owned_manifest.migrate(self.payload)
            database.assert_not_called()

    def test_persistence_is_private_idempotent_and_collision_safe(self) -> None:
        old_source = next(iter(migrate_owned_manifest.ALLOWED_LEGACY_SOURCE_SHA256))
        old_document = self.document(old_source)
        legacy_bytes = migrate_owned_manifest.encode_json(old_document)
        current_document = self.document(reset_owned.source_sha256())
        receipt = {
            "database_state": "absent",
            "legacy_manifest_sha256": hashlib.sha256(legacy_bytes).hexdigest(),
            "legacy_source_sha256": old_source,
            "migration_sha256": "1" * 64,
            "persistent_manifest_sha256": hashlib.sha256(
                migrate_owned_manifest.encode_json(current_document)
            ).hexdigest(),
            "reset_source_sha256": reset_owned.source_sha256(),
        }
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            destination.chmod(0o700)
            self.assertEqual(
                migrate_owned_manifest.persist_migration(
                    self.run_id, legacy_bytes, current_document, receipt, base_directory=destination
                ),
                3,
            )
            before = {path.name: path.read_bytes() for path in destination.iterdir()}
            self.assertEqual(
                migrate_owned_manifest.persist_migration(
                    self.run_id, legacy_bytes, current_document, receipt, base_directory=destination
                ),
                0,
            )
            self.assertEqual(before, {path.name: path.read_bytes() for path in destination.iterdir()})
            self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in destination.iterdir()))
            paths = migrate_owned_manifest.destination_paths(self.run_id, destination)
            paths["receipt"].write_bytes(b"different\n")
            paths["receipt"].chmod(0o600)
            with self.assertRaisesRegex(reset_owned.OwnedRunError, "persistent_collision"):
                migrate_owned_manifest.persist_migration(
                    self.run_id, legacy_bytes, current_document, receipt, base_directory=destination
                )

    def test_crash_resume_accepts_only_identical_completed_phases(self) -> None:
        old_source = next(iter(migrate_owned_manifest.ALLOWED_LEGACY_SOURCE_SHA256))
        legacy_bytes = migrate_owned_manifest.encode_json(self.document(old_source))
        current_document = self.document(reset_owned.source_sha256())
        receipt = {"phase": "reviewed", "sha256": "2" * 64}
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            destination.chmod(0o700)
            paths = migrate_owned_manifest.destination_paths(self.run_id, destination)
            self.assertTrue(migrate_owned_manifest.write_or_verify_private(paths["legacy"], legacy_bytes))
            self.assertEqual(
                migrate_owned_manifest.persist_migration(
                    self.run_id, legacy_bytes, current_document, receipt, base_directory=destination
                ),
                2,
            )
            self.assertEqual(paths["legacy"].read_bytes(), legacy_bytes)


if __name__ == "__main__":
    unittest.main()
