#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import stat
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import reset_owned


class ResetOwnedSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = "a1" * 12
        self.actor_a = str(uuid.uuid4())
        self.actor_b = str(uuid.uuid4())

    def payload(self, **changes: str) -> str:
        value = {"run_id": self.run_id, "actor_a": self.actor_a, "actor_b": self.actor_b}
        value.update(changes)
        return json.dumps(value)

    def test_parser_accepts_only_exact_valid_shape_and_different_actors(self) -> None:
        parsed = reset_owned.parse_stdin_payload(self.payload(), self.run_id)
        self.assertEqual(parsed, {"run_id": self.run_id, "actor_a": self.actor_a, "actor_b": self.actor_b})
        with self.assertRaisesRegex(reset_owned.OwnedRunError, "actors_must_differ"):
            reset_owned.parse_stdin_payload(self.payload(actor_b=self.actor_a), self.run_id)
        extra = json.loads(self.payload())
        extra["key"] = "must-not-be-accepted"
        with self.assertRaisesRegex(reset_owned.OwnedRunError, "invalid_input_shape"):
            reset_owned.parse_stdin_payload(json.dumps(extra), self.run_id)

    def test_run_id_rejects_path_traversal_and_cli_mismatch(self) -> None:
        with self.assertRaisesRegex(reset_owned.OwnedRunError, "invalid_run_id"):
            reset_owned.manifest_path("../escape")
        with self.assertRaisesRegex(reset_owned.OwnedRunError, "run_id_mismatch"):
            reset_owned.parse_stdin_payload(self.payload(), "b2" * 12)

    def test_persistent_path_uses_passwd_home_and_not_temporary_storage(self) -> None:
        directory = reset_owned.persistent_manifest_directory()
        self.assertTrue(directory.is_absolute())
        self.assertEqual(directory.name, "sns-d4-owned-runs")
        self.assertEqual(directory.parent.name, "state")
        self.assertNotEqual(directory.parts[1:2], ("tmp",))

    def test_manifest_directory_rejects_symlink_and_nonprivate_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir(mode=0o700)
            symlink = root / "link"
            symlink.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(reset_owned.OwnedRunError, "manifest_directory_rejected"):
                reset_owned.ensure_manifest_directory(symlink)
            target.chmod(0o755)
            with self.assertRaisesRegex(reset_owned.OwnedRunError, "manifest_directory_rejected"):
                reset_owned.ensure_manifest_directory(target)

    def test_database_binding_requires_exact_loopback_mapping(self) -> None:
        reset_owned.validate_database_binding({"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "54322"}]})
        rejected = (
            {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "54322"}]},
            {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "9999"}]},
            {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "54322"}], "9999/tcp": []},
        )
        for binding in rejected:
            with self.subTest(binding=binding), self.assertRaisesRegex(
                reset_owned.OwnedRunError, "database_binding_rejected"
            ):
                reset_owned.validate_database_binding(binding)

    def test_exclusive_manifest_reservation_preserves_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path = reset_owned.manifest_path(self.run_id, base)
            document = reset_owned.manifest_document(
                {"actor_a": self.actor_a, "actor_b": self.actor_b},
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
            _, first_hash = reset_owned.reserve_manifest(path, document)
            original = path.read_bytes()
            with self.assertRaisesRegex(reset_owned.OwnedRunError, "manifest_exists"):
                reset_owned.reserve_manifest(path, document)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(first_hash, hashlib.sha256(original).hexdigest())

    def test_manifest_rejects_actor_or_post_aliasing(self) -> None:
        document = {
            "source_sha256": "0" * 64,
            "actors": {"a": self.actor_a, "b": self.actor_a},
            "posts": {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())},
        }
        with self.assertRaisesRegex(reset_owned.OwnedRunError, "manifest_rejected"):
            reset_owned.validate_manifest(document)

    def test_seed_retains_manifest_when_database_outcome_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / f"{self.run_id}.json"
            payload = {"run_id": self.run_id, "actor_a": self.actor_a, "actor_b": self.actor_b}
            with (
                mock.patch.object(reset_owned, "verify_dedicated_database"),
                mock.patch.object(reset_owned, "validate_profiles"),
                mock.patch.object(reset_owned, "validate_foreign_key_contract"),
                mock.patch.object(reset_owned, "ensure_manifest_directory"),
                mock.patch.object(reset_owned, "manifest_path", return_value=path),
                mock.patch.object(reset_owned, "run_psql", side_effect=TimeoutError("after commit is unknown")),
            ):
                with self.assertRaisesRegex(
                    reset_owned.OwnedRunError, "seed_requires_database_reconciliation"
                ):
                    reset_owned.seed(payload)
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            reset_owned.validate_manifest(json.loads(path.read_text()))

    def test_stale_source_manifest_rejects_reset_before_sql(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / f"{self.run_id}.json"
            document = {
                "source_sha256": "0" * 64,
                "actors": {"a": self.actor_a, "b": self.actor_b},
                "posts": {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())},
            }
            path.write_text(json.dumps(document))
            path.chmod(0o600)
            payload = {"run_id": self.run_id, "actor_a": self.actor_a, "actor_b": self.actor_b}
            with (
                mock.patch.object(reset_owned, "verify_dedicated_database"),
                mock.patch.object(reset_owned, "ensure_manifest_directory"),
                mock.patch.object(reset_owned, "manifest_path", return_value=path),
                mock.patch.object(reset_owned, "run_psql") as database,
            ):
                with self.assertRaisesRegex(reset_owned.OwnedRunError, "manifest_source_mismatch"):
                    reset_owned.reset(payload)
            database.assert_not_called()


if __name__ == "__main__":
    unittest.main()
