#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from d4_typecheck import (
    D4TypecheckError,
    FixedD4Typecheck,
    PROFILE_ID,
    _dependency_roots,
)
from verify_d4_chapter_build import reconstruct_from_chapter


class D4TypecheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidate = Path(__file__).resolve().parents[1] / "candidates/d4-runtime"
        cls.overlay = Path(os.environ.get("D4_TEST_DEPENDENCIES", "/tmp/sns-auth-sdk57-runtime/node_modules"))
        try:
            cls.node = Path(subprocess.check_output(
                ["node", "-p", "process.execPath"], text=True, timeout=10
            ).strip())
        except (OSError, subprocess.SubprocessError):
            cls.node = Path("/not-ready/node")
        roots: set[Path] = set()
        if cls.overlay.is_dir():
            for path in cls.overlay.rglob("*"):
                if path.is_symlink():
                    target = path.resolve(strict=True)
                    ancestors = [target, *target.parents]
                    root = next((item for item in ancestors if item.name == "node_modules"), None)
                    if root is not None:
                        roots.add(root)
        cls.targets = tuple(Path(p) for p in json.loads(os.environ["D4_TEST_TARGETS"])) if "D4_TEST_TARGETS" in os.environ else tuple(sorted(roots))

    def require_runtime(self) -> None:
        overrides_incomplete = ("D4_TEST_DEPENDENCIES" in os.environ) != ("D4_TEST_TARGETS" in os.environ)
        if overrides_incomplete or not Path("/usr/bin/bwrap").is_file() or not self.node.is_file() or not self.overlay.is_dir() or not self.targets:
            if os.environ.get("D4_REQUIRE_REAL_TOOLCHAIN") == "1":
                self.fail("Required real toolchain unavailable or overrides incomplete")
            self.skipTest("NOT_READY: fixed bwrap, Node, and SDK57 roots with complete overrides are required")

    def checker(self, app: Path, timeout: float = 60) -> FixedD4Typecheck:
        return FixedD4Typecheck(
            app, self.overlay, node_executable=self.node,
            dependency_targets=self.targets, timeout_seconds=timeout,
        )

    def copy_starter(self, destination: Path) -> Path:
        app = destination / "app"
        shutil.copytree(self.candidate / "start", app)
        return app

    def write_reconstructed(self, destination: Path) -> Path:
        app = destination / "app"
        app.mkdir(parents=True)
        files, _receipt = reconstruct_from_chapter(self.candidate)
        for relative, content in files.items():
            target = app / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return app

    def test_api_has_no_argv_or_environment_and_rejects_unknown_profile(self) -> None:
        parameters = tuple(inspect.signature(FixedD4Typecheck.run).parameters)
        self.assertEqual(parameters, ("self", "profile_id"))
        with tempfile.TemporaryDirectory() as temporary:
            app = self.copy_starter(Path(temporary))
            checker = self.checker(app)
            with self.assertRaisesRegex(D4TypecheckError, "unknown_profile"):
                checker.run("model-selected-profile")
        for timeout in (0, 61, True):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(D4TypecheckError, "invalid_timeout"):
                FixedD4Typecheck(
                    Path("/unused"), self.overlay, node_executable=self.node,
                    dependency_targets=self.targets, timeout_seconds=timeout,
                )

    def test_source_inventory_rejects_private_symlink_and_extra_typescript(self) -> None:
        self.require_runtime()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, create in (
                ("private", lambda app: (app / ".env").write_text("SECRET=x")),
                ("extra_ts", lambda app: (app / "model-plugin.ts").write_text("export {}")),
                ("symlink", lambda app: (app / "escape").symlink_to("/etc/passwd")),
            ):
                app = self.copy_starter(root / name)
                create(app)
                with self.subTest(name=name), self.assertRaises(D4TypecheckError):
                    self.checker(app).run(PROFILE_ID)

    def test_dependency_overlay_rejects_unpermitted_absolute_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            overlay = Path(temporary) / "node_modules"
            overlay.mkdir()
            (overlay / "escape").symlink_to("/etc/passwd")
            with self.assertRaisesRegex(D4TypecheckError, "dependency_symlink_rejected"):
                _dependency_roots(overlay, self.targets or (overlay,))

    def test_actual_bwrap_typechecks_starter_and_reconstructed_app(self) -> None:
        self.require_runtime()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            starter = self.checker(self.copy_starter(root / "starter")).run(PROFILE_ID)
            reconstructed = self.checker(self.write_reconstructed(root / "final")).run(PROFILE_ID)
        for receipt, expected_files in ((starter, 19), (reconstructed, 20)):
            with self.subTest(expected_files=expected_files):
                self.assertTrue(receipt.passed)
                self.assertEqual(receipt.exit_code, 0)
                self.assertEqual(receipt.diagnostics, ())
                self.assertEqual(receipt.scope, "D4_ISOLATED_TYPECHECK_NOT_INDEPENDENT_EXEC")
                self.assertFalse(receipt.model_or_ui_run)
                self.assertEqual(len(receipt.isolation_checks), 9)
                self.assertIn("network_blocked", receipt.isolation_checks)
                self.assertIn("host_paths_hidden", receipt.isolation_checks)
                self.assertIn("app_read_only", receipt.isolation_checks)
                with self.assertRaises(FrozenInstanceError):
                    receipt.exit_code = 9  # type: ignore[misc]

    def test_actual_type_error_is_sanitized_and_source_is_unchanged(self) -> None:
        self.require_runtime()
        with tempfile.TemporaryDirectory() as temporary:
            app = self.write_reconstructed(Path(temporary))
            app_file = app / "App.tsx"
            app_file.write_text(app_file.read_text() + "\nconst d4TypeError: string = 1;\n")
            before = app_file.read_bytes()
            receipt = self.checker(app).run(PROFILE_ID)
            after = app_file.read_bytes()
        self.assertFalse(receipt.passed)
        self.assertNotEqual(receipt.exit_code, 0)
        self.assertEqual(before, after)
        self.assertTrue(receipt.diagnostics)
        rendered = repr(receipt.diagnostics)
        self.assertNotIn(str(app), rendered)
        self.assertNotIn("d4TypeError", rendered)
        self.assertTrue(all(len(item.message_sha256) == 64 for item in receipt.diagnostics))


if __name__ == "__main__":
    unittest.main()
