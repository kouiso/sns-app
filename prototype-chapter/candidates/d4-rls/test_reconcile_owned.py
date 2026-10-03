#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import reconcile_owned
import reset_owned


class ReconcileOwnedTests(unittest.TestCase):
    def test_status_classification(self) -> None:
        self.assertEqual(reconcile_owned.classify_post_state(0, 0, 0), "absent")
        self.assertEqual(reconcile_owned.classify_post_state(1, 1, 0), "partial")
        self.assertEqual(reconcile_owned.classify_post_state(2, 2, 0), "seeded")
        self.assertEqual(reconcile_owned.classify_post_state(1, 0, 1), "conflict")
        self.assertEqual(reconcile_owned.classify_post_state(2, 1, 1), "conflict")
        with self.assertRaisesRegex(reset_owned.OwnedRunError, "invalid_reconciliation_counts"):
            reconcile_owned.classify_post_state(2, 0, 1)

    def test_generated_sql_is_read_only_and_manifest_is_unchanged(self) -> None:
        run_id = "ab" * 12
        document = {
            "source_sha256": reset_owned.source_sha256(),
            "actors": {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())},
            "posts": {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / f"{run_id}.json"
            path.write_text(json.dumps(document, sort_keys=True))
            path.chmod(0o600)
            before = path.read_bytes()
            sql = reconcile_owned.reconciliation_sql(document, run_id)
            after = path.read_bytes()
        normalized = " ".join(sql.lower().split())
        self.assertIn("begin transaction read only", normalized)
        self.assertIn("select pg_try_advisory_xact_lock", normalized)
        self.assertTrue(normalized.endswith("rollback;"))
        for forbidden in (" insert ", " update ", " delete ", " truncate ", " alter ", " drop ", " commit"):
            self.assertNotIn(forbidden, f" {normalized} ")
        self.assertEqual(before, after)

    def test_stale_source_returns_no_invented_counts_and_never_queries_rows(self) -> None:
        run_id = "cd" * 12
        actors = {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())}
        document = {
            "source_sha256": "0" * 64,
            "actors": actors,
            "posts": {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())},
        }
        payload = {"run_id": run_id, "actor_a": actors["a"], "actor_b": actors["b"]}
        with (
            mock.patch.object(reset_owned, "verify_dedicated_database"),
            mock.patch.object(reset_owned, "ensure_manifest_directory"),
            mock.patch.object(reset_owned, "manifest_path"),
            mock.patch.object(reset_owned, "read_manifest", return_value=(document, "f" * 64)),
            mock.patch.object(reset_owned, "run_psql") as database,
        ):
            with self.assertRaisesRegex(reset_owned.OwnedRunError, "manifest_source_mismatch"):
                reconcile_owned.reconcile(payload)
        database.assert_not_called()


if __name__ == "__main__":
    unittest.main()
