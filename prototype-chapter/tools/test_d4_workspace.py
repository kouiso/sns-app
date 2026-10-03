from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from d4_workspace import D4Workspace, MAX_CONTENT_BYTES, WorkspaceError


CANDIDATE = Path(__file__).resolve().parents[1] / "candidates" / "d4-runtime"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class D4WorkspaceTests(unittest.TestCase):
    def create(self, temporary: str) -> tuple[D4Workspace, Path]:
        root = Path(temporary) / "workspace"
        return D4Workspace.create(CANDIDATE, root), root

    def test_read_inventory_and_snapshot_expose_only_public_relative_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, root = self.create(temporary)
            read = workspace.read_file({"path": "app/README.md"})
            self.assertIn("Auth", read["content"])
            self.assertFalse(read["editable"])
            inventory = workspace.verify_inventory()
            self.assertEqual(len(inventory["files"]), 20)
            self.assertFalse(inventory["component_present"])
            snapshot = workspace.snapshot()
            self.assertEqual([item["path"] for item in snapshot["files"]], ["app/App.tsx"])
            rendered = repr((read, inventory, snapshot))
            self.assertNotIn(str(root), rendered)
            self.assertNotIn(str(CANDIDATE), rendered)

    def test_create_rejects_changed_frozen_candidate_source(self) -> None:
        for relative in ("start/README.md", "chapter-build.md"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                candidate = Path(temporary) / "candidate"
                shutil.copytree(CANDIDATE, candidate)
                (candidate / relative).write_text("changed", encoding="utf-8")
                with self.assertRaises(WorkspaceError):
                    D4Workspace.create(candidate, Path(temporary) / "workspace")

    def test_model_can_cas_edit_app_and_create_then_edit_component(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _ = self.create(temporary)
            app = workspace.read_file({"path": "app/App.tsx"})
            app_text = str(app["content"]) + "\n// learner edit\n"
            app_result = workspace.edit_file(
                {
                    "path": "app/App.tsx",
                    "expected_sha256": app["sha256"],
                    "content": app_text,
                }
            )
            self.assertEqual(app_result["sha256"], digest(app_text))

            first = "export const learnerChoice = 1;\n"
            created = workspace.edit_file(
                {
                    "path": "app/components/RlsTrial.tsx",
                    "expected_sha256": None,
                    "content": first,
                }
            )
            second = "export const learnerChoice = 2;\n"
            changed = workspace.edit_file(
                {
                    "path": "app/components/RlsTrial.tsx",
                    "expected_sha256": created["sha256"],
                    "content": second,
                }
            )
            self.assertEqual(changed["previous_sha256"], digest(first))
            self.assertEqual(workspace.read_file({"path": "app/components/RlsTrial.tsx"})["content"], second)
            self.assertEqual(
                [item["path"] for item in workspace.snapshot()["files"]],
                ["app/App.tsx", "app/components/RlsTrial.tsx"],
            )

    def test_external_editable_replacement_and_component_injection_are_rejected(self) -> None:
        mutations = (
            lambda root: (root / "app" / "App.tsx").write_text("external\n", encoding="utf-8"),
            lambda root: (
                (root / "app" / "components").mkdir(),
                (root / "app" / "components" / "RlsTrial.tsx").write_text(
                    "external\n", encoding="utf-8"
                ),
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temporary:
                workspace, root = self.create(temporary)
                mutate(root)
                with self.assertRaisesRegex(WorkspaceError, "workspace_tampered"):
                    workspace.verify_inventory()

    def test_authorized_output_restore_is_strict_and_correlated_to_current_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, root = self.create(temporary)
            app = workspace.read_file({"path": "app/App.tsx"})
            workspace.edit_file(
                {
                    "path": "app/App.tsx",
                    "expected_sha256": app["sha256"],
                    "content": "authorized app\n",
                }
            )
            workspace.edit_file(
                {
                    "path": "app/components/RlsTrial.tsx",
                    "expected_sha256": None,
                    "content": "authorized component\n",
                }
            )
            hashes = {
                item["path"]: item["sha256"] for item in workspace.snapshot()["files"]
            }
            restored = D4Workspace(root, workspace._start_hashes, hashes)  # controller-only restore
            self.assertEqual(restored.snapshot()["snapshot_sha256"], workspace.snapshot()["snapshot_sha256"])

            for rejected in (
                {"app/App.tsx": hashes["app/App.tsx"]},
                {**hashes, "extra": None},
                {**hashes, "app/App.tsx": None},
                {**hashes, "app/App.tsx": "0" * 64},
            ):
                with self.subTest(rejected=rejected):
                    with self.assertRaises(WorkspaceError):
                        D4Workspace(root, workspace._start_hashes, rejected)

    def test_authorized_restore_rejects_oversize_binary_and_control_outputs(self) -> None:
        invalid_values = (
            b"x" * (MAX_CONTENT_BYTES + 1),
            b"\xff\xfe",
            b"valid-prefix\x00invalid-control",
        )
        for content in invalid_values:
            with self.subTest(size=len(content)), tempfile.TemporaryDirectory() as temporary:
                workspace, root = self.create(temporary)
                app_path = root / "app" / "App.tsx"
                app_path.write_bytes(content)
                authorized = {
                    "app/App.tsx": hashlib.sha256(content).hexdigest(),
                    "app/components/RlsTrial.tsx": None,
                }
                with self.assertRaisesRegex(WorkspaceError, "workspace_tampered"):
                    D4Workspace(root, workspace._start_hashes, authorized)

    def test_outside_readonly_additional_fields_and_control_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _ = self.create(temporary)
            cases = (
                lambda: workspace.read_file({"path": "../chapter-build.md"}),
                lambda: workspace.read_file({"path": "/etc/passwd"}),
                lambda: workspace.read_file({"path": "app/README.md\x00"}),
                lambda: workspace.read_file({"path": "chapter.md", "extra": True}),
                lambda: workspace.edit_file(
                    {"path": "chapter.md", "expected_sha256": "a" * 64, "content": "x"}
                ),
                lambda: workspace.edit_file(
                    {
                        "path": "app/README.md",
                        "expected_sha256": "a" * 64,
                        "content": "x",
                    }
                ),
                lambda: workspace.edit_file(
                    {
                        "path": "app/App.tsx",
                        "expected_sha256": "a" * 64,
                        "content": "x",
                        "extra": True,
                    }
                ),
            )
            for operation in cases:
                with self.subTest(operation=operation):
                    with self.assertRaises(WorkspaceError):
                        operation()

    def test_stale_and_null_cas_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _ = self.create(temporary)
            with self.assertRaisesRegex(WorkspaceError, "expected_sha256_required"):
                workspace.edit_file(
                    {"path": "app/App.tsx", "expected_sha256": None, "content": "x"}
                )
            with self.assertRaisesRegex(WorkspaceError, "stale_cas"):
                workspace.edit_file(
                    {"path": "app/App.tsx", "expected_sha256": "0" * 64, "content": "x"}
                )
            created = workspace.edit_file(
                {
                    "path": "app/components/RlsTrial.tsx",
                    "expected_sha256": None,
                    "content": "first\n",
                }
            )
            with self.assertRaisesRegex(WorkspaceError, "expected_sha256_required"):
                workspace.edit_file(
                    {
                        "path": "app/components/RlsTrial.tsx",
                        "expected_sha256": None,
                        "content": "second\n",
                    }
                )
            with self.assertRaisesRegex(WorkspaceError, "stale_cas"):
                workspace.edit_file(
                    {
                        "path": "app/components/RlsTrial.tsx",
                        "expected_sha256": "0" * 64,
                        "content": "second\n",
                    }
                )
            self.assertEqual(created["sha256"], digest("first\n"))

    def test_frozen_source_tamper_extra_nodes_and_symlinks_fail_every_request(self) -> None:
        mutations = (
            lambda root: (root / "app" / "README.md").write_bytes(b"x" * 4603),
            lambda root: (
                (root / "chapter.md").chmod(0o600),
                (root / "chapter.md").write_text("changed", encoding="utf-8"),
            ),
            lambda root: (root / "app" / "extra.ts").write_text("extra", encoding="utf-8"),
            lambda root: (root / "unexpected").mkdir(),
            lambda root: (root / "app" / "lib" / "escape").symlink_to("/etc/passwd"),
            lambda root: os.mkfifo(root / "app" / "special"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temporary:
                workspace, root = self.create(temporary)
                readonly = root / "app" / "README.md"
                readonly.chmod(0o600)
                mutate(root)
                with self.assertRaisesRegex(WorkspaceError, "workspace_tampered"):
                    workspace.snapshot()

    def test_invalid_content_and_size_limits_are_rejected_without_changing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _ = self.create(temporary)
            app = workspace.read_file({"path": "app/App.tsx"})
            for content, code in (
                ("bad\x00source", "invalid_content"),
                ("x" * (MAX_CONTENT_BYTES + 1), "content_too_large"),
            ):
                with self.subTest(code=code):
                    with self.assertRaisesRegex(WorkspaceError, code):
                        workspace.edit_file(
                            {
                                "path": "app/App.tsx",
                                "expected_sha256": app["sha256"],
                                "content": content,
                            }
                        )
            self.assertEqual(workspace.read_file({"path": "app/App.tsx"})["sha256"], app["sha256"])
            with self.assertRaisesRegex(WorkspaceError, "request_too_large"):
                workspace.read_file({"path": "x" * (256 * 1024)})

    def test_binary_and_large_text_reads_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, _ = self.create(temporary)
            with self.assertRaisesRegex(WorkspaceError, "file_not_text"):
                workspace.read_file({"path": "app/assets/favicon.png"})
            with self.assertRaisesRegex(WorkspaceError, "content_too_large"):
                workspace.read_file({"path": "app/package-lock.json"})

    def test_atomic_replace_does_not_leave_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, root = self.create(temporary)
            app = workspace.read_file({"path": "app/App.tsx"})
            workspace.edit_file(
                {
                    "path": "app/App.tsx",
                    "expected_sha256": app["sha256"],
                    "content": "replacement\n",
                }
            )
            self.assertEqual((root / "app" / "App.tsx").read_text(), "replacement\n")
            self.assertEqual(list((root / "app").glob(".d4-edit-*")), [])


if __name__ == "__main__":
    unittest.main()
