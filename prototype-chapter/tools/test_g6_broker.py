from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from g6_broker import BrokerError, execute_manifest, snapshot_digest


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.inputs = self.base / "inputs"
        self.workspace = self.base / "work"
        self.inputs.mkdir()
        self.workspace.mkdir()
        (self.inputs / "starter").mkdir()
        self.start_data = b"starter\n"
        (self.inputs / "starter" / "README.md").write_bytes(self.start_data)
        self.chapter = (
            "# Trial\n"
            "G6_ACTION: step-one make-src-directory\n"
            "G6_MKDIR: src\n"
            "G6_ACTION: step-two write-broker-probe\n"
            'G6_WRITE: {"path":"src/g6-broker-probe.txt",'
            '"utf8":"G6 broker probe\\n"}\n'
            "G6_ACTION: step-three read-python-version\n"
            'G6_ARGV: ["/usr/bin/python3","--version"]\n'
        ).encode()
        (self.inputs / "chapter.md").write_bytes(self.chapter)
        self.manifest_path = self.base / "manifest.json"
        self.manifest: dict[str, Any] = {
            "version": 1,
            "chapter": {"path": "chapter.md", "sha256": sha(self.chapter)},
            "start": {
                "root": "starter",
                "files": [{"path": "README.md", "sha256": sha(self.start_data)}],
                "snapshot_sha256": snapshot_digest(
                    [("README.md", self.start_data)]
                ),
            },
            "artifact_id": "trial-artifact",
            "actions": [
                self.action("step-one", "make-src-directory", 2),
                self.action("step-two", "write-broker-probe", 4),
                self.action("step-three", "read-python-version", 6),
            ],
        }
        self.write_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def action(self, action_id: str, operation: str, line: int) -> dict[str, object]:
        lines = self.chapter.decode().splitlines(keepends=True)
        excerpt = "".join(lines[line - 1 : line + 1]).encode()
        return {
            "id": action_id,
            "operation": operation,
            "source": {
                "path": "chapter.md",
                "start_line": line,
                "end_line": line + 1,
                "sha256": sha(excerpt),
            },
        }

    def write_manifest(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self.manifest, ensure_ascii=False), encoding="utf-8"
        )

    def execute(self) -> dict[str, Any]:
        return execute_manifest(self.manifest_path, self.inputs, self.workspace)

    def test_real_bwrap_executes_fixed_operations_and_binds_hashes(self) -> None:
        receipt: dict[str, Any] = self.execute()
        trace = receipt["trace"]
        self.assertEqual(7, len(trace["preflight"]))
        self.assertTrue(all(trace["preflight"].values()))
        self.assertEqual("G6_BROKER_PROBE_COMPONENT_NON_FORMAL", trace["scope"])
        self.assertEqual(
            {
                "formal_g6_exec": False,
                "knowledge_isolation": False,
                "ui_validated": False,
            },
            trace["claims"],
        )
        self.assertEqual(sha(self.chapter), trace["chapter_sha256"])
        self.assertEqual(
            self.manifest["start"]["snapshot_sha256"],
            trace["start_snapshot_sha256"],
        )
        self.assertRegex(receipt["trace_sha256"], r"^[0-9a-f]{64}$")
        for field in (
            "broker_source_sha256",
            "probe_source_sha256",
            "operation_table_sha256",
            "bwrap_sha256",
            "kernel_release_sha256",
            "sandbox_recipe_sha256",
        ):
            self.assertRegex(trace[field], r"^[0-9a-f]{64}$")
        self.assertEqual(self.start_data, (self.workspace / "README.md").read_bytes())
        self.assertTrue((self.workspace / "src").is_dir())
        self.assertEqual(
            b"G6 broker probe\n",
            (self.workspace / "src" / "g6-broker-probe.txt").read_bytes(),
        )
        command = trace["actions"][2]
        self.assertEqual(0, command["exit_code"])
        self.assertNotIn("stdout", command)

    def test_manifest_cannot_supply_argv_contents_or_unknown_operations(self) -> None:
        self.manifest["actions"][0]["argv"] = ["/bin/sh", "-c", "id"]
        self.write_manifest()
        with self.assertRaisesRegex(BrokerError, "fields differ"):
            self.execute()

        self.workspace = self.base / "work-two"
        self.workspace.mkdir()
        self.manifest["actions"][0].pop("argv")
        self.manifest["actions"][0]["operation"] = "arbitrary-shell"
        self.write_manifest()
        with self.assertRaisesRegex(BrokerError, "unknown operation"):
            self.execute()

    def test_source_span_and_whole_chapter_are_both_bound(self) -> None:
        altered = self.chapter.replace(b"G6_MKDIR: src", b"G6_MKDIR: lib")
        (self.inputs / "chapter.md").write_bytes(altered)
        self.manifest["chapter"]["sha256"] = sha(altered)
        altered_excerpt = b"G6_ACTION: step-one make-src-directory\nG6_MKDIR: lib\n"
        self.manifest["actions"][0]["source"]["sha256"] = sha(altered_excerpt)
        self.write_manifest()
        with self.assertRaisesRegex(BrokerError, "exact operation"):
            self.execute()

        self.workspace = self.base / "work-two"
        self.workspace.mkdir()
        (self.inputs / "chapter.md").write_bytes(self.chapter)
        self.manifest["chapter"]["sha256"] = sha(self.chapter)
        self.manifest["actions"][0] = self.action(
            "step-one", "make-src-directory", 2
        )
        (self.inputs / "chapter.md").write_bytes(self.chapter + b"changed\n")
        self.write_manifest()
        with self.assertRaisesRegex(BrokerError, "chapter hash mismatch"):
            self.execute()

    def test_json_is_closed_and_rejects_duplicate_nan_bool_and_empty_actions(self) -> None:
        raw = self.manifest_path.read_text(encoding="utf-8")
        self.manifest_path.write_text(raw[:-1] + ',"version":1}', encoding="utf-8")
        with self.assertRaisesRegex(BrokerError, "duplicate JSON field"):
            self.execute()

        cases = [
            {**self.manifest, "version": True},
            {**self.manifest, "version": float("nan")},
            {**self.manifest, "actions": []},
            {**self.manifest, "extra": "ignored"},
        ]
        for index, case in enumerate(cases):
            self.workspace = self.base / f"case-{index}"
            self.workspace.mkdir()
            self.manifest = case
            self.write_manifest()
            with self.assertRaises(BrokerError):
                self.execute()

    def test_unsafe_paths_hash_mismatch_and_symlinks_fail_closed(self) -> None:
        unsafe = ("../chapter.md", "/chapter.md", "C:/chapter.md", "a\\b.md", "./x")
        for index, path in enumerate(unsafe):
            self.workspace = self.base / f"unsafe-{index}"
            self.workspace.mkdir()
            self.manifest["chapter"]["path"] = path
            self.write_manifest()
            with self.assertRaises(BrokerError):
                self.execute()
        self.manifest["chapter"]["path"] = "chapter.md"
        self.manifest["chapter"]["sha256"] = "0" * 64
        self.workspace = self.base / "bad-hash"
        self.workspace.mkdir()
        self.write_manifest()
        with self.assertRaisesRegex(BrokerError, "hash mismatch"):
            self.execute()

        self.manifest["chapter"]["sha256"] = sha(self.chapter)
        (self.inputs / "chapter.md").unlink()
        (self.inputs / "chapter.md").symlink_to("starter/README.md")
        self.workspace = self.base / "symlink-input"
        self.workspace.mkdir()
        self.write_manifest()
        with self.assertRaisesRegex(BrokerError, "symlink"):
            self.execute()

    def test_workspace_must_be_empty_and_fixed_bwrap_must_exist(self) -> None:
        (self.workspace / "stale").write_text("old", encoding="utf-8")
        with self.assertRaisesRegex(BrokerError, "workspace must be empty"):
            self.execute()

        self.workspace = self.base / "fresh"
        self.workspace.mkdir()
        fake_bwrap = self.base / "fake-bwrap"
        fake_bwrap.write_text("#!/bin/sh\necho forged preflight\n", encoding="utf-8")
        fake_bwrap.chmod(0o755)
        with patch("g6_broker.BWRAP_PATH", fake_bwrap):
            with self.assertRaisesRegex(BrokerError, "fixed /usr/bin/bwrap"):
                self.execute()


if __name__ == "__main__":
    unittest.main()
