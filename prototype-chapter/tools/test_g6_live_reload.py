from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from g6_live_reload import (
    COMMIT_MESSAGE,
    FINAL_APP_SHA256,
    LiveReloadError,
    LiveReloadSession,
    RESTORE_PRACTICE_TEXT,
    SDK57_EXECUTION_PROFILE,
    SDK57_PROFILE,
    _execution_profile,
    _read_fixed_source_tree,
    compile_sdk57_plan,
    run_all,
)


TOOLS = Path(__file__).resolve().parent
PROTOTYPE = TOOLS.parent
SDK57_CANDIDATE = PROTOTYPE / "candidates" / "sdk57"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SDK57SourceValidationTests(unittest.TestCase):
    def copy_source(self, root: Path) -> Path:
        source = root / "source"
        shutil.copytree(SDK57_CANDIDATE / "start-source", source)
        return source

    def test_sdk57_source_is_exact_regular_14_file_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = self.copy_source(Path(directory))
            files = _read_fixed_source_tree(
                source, SDK57_EXECUTION_PROFILE.start_files, require_git=False
            )
            self.assertEqual(14, len(files))
            self.assertEqual(
                sorted(dict(SDK57_EXECUTION_PROFILE.start_files)), sorted(files)
            )

    def test_sdk57_source_rejects_extra_missing_tampered_and_symlink(self) -> None:
        cases = ("extra", "missing", "tampered", "symlink")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                source = self.copy_source(Path(directory))
                if case == "extra":
                    (source / "extra.txt").write_text("extra", encoding="utf-8")
                    pattern = "exactly"
                elif case == "missing":
                    (source / "package.json").unlink()
                    pattern = "exactly"
                elif case == "tampered":
                    (source / "package.json").write_text("{}", encoding="utf-8")
                    pattern = "hash mismatch: package.json"
                else:
                    (source / "package.json").unlink()
                    (source / "package.json").symlink_to("App.tsx")
                    pattern = "symlink is forbidden"
                with self.assertRaisesRegex(LiveReloadError, pattern):
                    _read_fixed_source_tree(
                        source,
                        SDK57_EXECUTION_PROFILE.start_files,
                        require_git=False,
                    )

    def test_sdk57_chapter_and_profile_are_closed_allowlists(self) -> None:
        chapter = SDK57_CANDIDATE / "chapter-live-reload.md"
        start_app = (SDK57_CANDIDATE / "start-source" / "App.tsx").read_bytes()
        operations, _ = compile_sdk57_plan(chapter, start_app, SDK57_EXECUTION_PROFILE)
        self.assertEqual("write-complete-app", operations[0].operation_id)
        self.assertEqual(13, len(operations))

        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "chapter.md"
            stale.write_bytes(chapter.read_bytes() + b"\n")
            with self.assertRaisesRegex(LiveReloadError, "chapter revision"):
                compile_sdk57_plan(stale, start_app, SDK57_EXECUTION_PROFILE)
        with self.assertRaisesRegex(LiveReloadError, "chapter revision"):
            compile_sdk57_plan(
                PROTOTYPE / "chapter-live-reload.md",
                start_app,
                SDK57_EXECUTION_PROFILE,
            )
        with self.assertRaisesRegex(LiveReloadError, "unknown fixed"):
            _execution_profile("sdk58")


class LiveReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        if not os.access("/usr/bin/bwrap", os.X_OK):
            self.skipTest("NOT_READY: live-reload component needs /usr/bin/bwrap")
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.chapter = self.base / "chapter-live-reload.md"
        self.chapter.write_bytes((PROTOTYPE / "chapter-live-reload.md").read_bytes())
        self.start = self.base / "start"
        self.start.mkdir()
        shutil.copy2(
            PROTOTYPE / "listings" / "expo-first-screen" / "App.tsx",
            self.start / "App.tsx",
        )
        self.git("init", cwd=self.start)
        self.git("config", "--local", "user.name", "G6 Fixture", cwd=self.start)
        self.git(
            "config", "--local", "user.email", "g6@example.invalid", cwd=self.start
        )
        self.git("add", "App.tsx", cwd=self.start)
        self.git("commit", "-m", "start", cwd=self.start)
        self.workspace = self.base / "work"
        self.evidence = self.base / "evidence"
        self.workspace.mkdir()
        self.evidence.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str, cwd: Path) -> str:
        result = subprocess.run(
            ["/usr/bin/git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin", "HOME": str(self.base / "host-home")},
        )
        return result.stdout

    def session(self) -> LiveReloadSession:
        return LiveReloadSession(
            self.chapter, self.start, self.workspace, self.evidence
        )

    def test_real_bwrap_executes_fixed_app_git_and_restore_stages(self) -> None:
        with self.session() as session:
            receipt = run_all(session)
        self.assertEqual(
            FINAL_APP_SHA256, sha((self.workspace / "App.tsx").read_bytes())
        )
        self.assertEqual("", self.git("status", "--porcelain", cwd=self.workspace))
        self.assertEqual(
            COMMIT_MESSAGE,
            self.git("log", "-1", "--pretty=%s", cwd=self.workspace).strip(),
        )
        self.assertEqual(
            ["App.tsx"],
            self.git(
                "show", "--pretty=", "--name-only", "HEAD", cwd=self.workspace
            ).splitlines(),
        )
        self.assertTrue((self.evidence / "text" / "App.tsx").is_file())
        self.assertTrue((self.evidence / "style" / "App.tsx").is_file())
        dirty = (self.evidence / "restore-practice-dirty" / "App.tsx").read_text()
        self.assertIn(RESTORE_PRACTICE_TEXT, dirty)
        self.assertEqual(
            (self.evidence / "committed" / "App.tsx").read_bytes(),
            (self.evidence / "git-restored" / "App.tsx").read_bytes(),
        )
        trace = receipt["trace"]
        self.assertTrue(trace["claims"]["artifact_git_execution"])
        for claim in (
            "formal_g6_exec",
            "model_mcp_connected",
            "metro_executed",
            "ui_validated",
        ):
            self.assertFalse(trace["claims"][claim])
        self.assertEqual(11, len(trace["actions"]))
        self.assertEqual(64, len(trace["component_source_sha256"]))
        self.assertEqual(64, len(trace["broker_source_sha256"]))
        phase_actions = [action for action in trace["actions"] if action["phase"]]
        self.assertEqual(5, len(phase_actions))
        self.assertTrue(
            all(len(action["phase_snapshot_sha256"]) == 64 for action in phase_actions)
        )
        self.assertTrue((self.evidence / "trace.json").is_file())

    def test_unknown_shell_skip_and_repeat_requests_are_rejected(self) -> None:
        with self.session() as session:
            with self.assertRaisesRegex(LiveReloadError, "order violation"):
                session.request("sh -c id")
            self.assertFalse(session.failed)
            self.assertFalse(session.closed)
            with self.assertRaisesRegex(LiveReloadError, "order violation"):
                session.request("write-note-style")
            session.request("write-app-function")
            with self.assertRaisesRegex(LiveReloadError, "order violation"):
                session.request("write-app-function")

    def test_execution_failure_closes_session_and_exact_write_is_required(self) -> None:
        with self.session() as session:

            def wrong_write(_content: bytes) -> None:
                (self.workspace / "App.tsx").write_bytes(b"wrong")

            with mock.patch.object(session, "_write", side_effect=wrong_write):
                with self.assertRaisesRegex(LiveReloadError, "exact bytes"):
                    session.request("write-app-function")
            self.assertTrue(session.failed)
            self.assertTrue(session.closed)
            self.assertIn("exact bytes", session.failure_reason)
            self.assertIsNone(session.next_operation_id)
            with self.assertRaisesRegex(LiveReloadError, "session is closed"):
                session.request("write-app-function")

    def test_interrupted_write_still_closes_and_marks_session_failed(self) -> None:
        with self.session() as session:

            def interrupted_write(_content: bytes) -> None:
                (self.workspace / "App.tsx").write_bytes(b"partial")
                raise KeyboardInterrupt

            with mock.patch.object(session, "_write", side_effect=interrupted_write):
                with self.assertRaises(KeyboardInterrupt):
                    session.request("write-app-function")
            self.assertTrue(session.failed)
            self.assertTrue(session.closed)
            self.assertEqual("KeyboardInterrupt", session.failure_reason)

    def test_stale_chapter_start_extra_content_and_symlink_fail_closed(self) -> None:
        self.chapter.write_bytes(self.chapter.read_bytes() + b"\n")
        with self.assertRaisesRegex(LiveReloadError, "chapter revision"):
            self.session()
        self.chapter.write_bytes((PROTOTYPE / "chapter-live-reload.md").read_bytes())

        (self.start / "App.tsx").write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(LiveReloadError, "start App.tsx"):
            self.session()
        shutil.copy2(
            PROTOTYPE / "listings" / "expo-first-screen" / "App.tsx",
            self.start / "App.tsx",
        )
        (self.start / "extra.txt").write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(LiveReloadError, "exactly"):
            self.session()
        (self.start / "extra.txt").unlink()
        (self.start / "link").symlink_to("App.tsx")
        with self.assertRaisesRegex(LiveReloadError, "unsupported"):
            self.session()

    def test_dirty_restore_cannot_be_faked_by_a_noop(self) -> None:
        with self.session() as session:
            while session.next_operation_id != "git-status-before-restore":
                assert session.next_operation_id is not None
                session.request(session.next_operation_id)
            (self.workspace / "App.tsx").write_bytes(
                (PROTOTYPE / "listings" / "live-reload" / "App.tsx").read_bytes()
            )
            with self.assertRaisesRegex(
                LiveReloadError, "did not show App.tsx modified"
            ):
                session.request("git-status-before-restore")

    def test_start_must_be_clean_owned_repo_with_local_identity(self) -> None:
        (self.start / "App.tsx").write_bytes(
            (PROTOTYPE / "listings" / "live-reload" / "App.tsx").read_bytes()
        )
        with self.assertRaisesRegex(LiveReloadError, "start App.tsx"):
            self.session()

        shutil.copy2(
            PROTOTYPE / "listings" / "expo-first-screen" / "App.tsx",
            self.start / "App.tsx",
        )
        self.git("config", "--local", "--unset", "user.email", cwd=self.start)
        with self.assertRaisesRegex(LiveReloadError, "user.email"):
            self.session()

    def test_start_rejects_commondir_index_flags_and_head_blob_mismatch(self) -> None:
        commondir = self.start / ".git" / "commondir"
        commondir.write_text(".git\n", encoding="utf-8")
        with self.assertRaisesRegex(LiveReloadError, "commondir"):
            self.session()
        self.assertTrue(any(self.workspace.iterdir()))

        commondir.unlink()
        shutil.rmtree(self.workspace)
        self.workspace.mkdir()
        self.git("update-index", "--skip-worktree", "App.tsx", cwd=self.start)
        with self.assertRaisesRegex(LiveReloadError, "normal Git index flags"):
            self.session()

        self.git("update-index", "--no-skip-worktree", "App.tsx", cwd=self.start)
        shutil.rmtree(self.workspace)
        self.workspace.mkdir()
        (self.start / "App.tsx").write_text("wrong HEAD", encoding="utf-8")
        self.git("add", "App.tsx", cwd=self.start)
        self.git("commit", "--amend", "--no-edit", cwd=self.start)
        shutil.copy2(
            PROTOTYPE / "listings" / "expo-first-screen" / "App.tsx",
            self.start / "App.tsx",
        )
        with self.assertRaisesRegex(LiveReloadError, "start HEAD App.tsx"):
            self.session()

    def test_executable_git_hook_and_unsupported_local_config_are_rejected(
        self,
    ) -> None:
        hook = self.start / ".git" / "hooks" / "post-commit"
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        hook.chmod(0o755)
        with self.assertRaisesRegex(LiveReloadError, "hooks"):
            self.session()
        hook.unlink()
        shutil.rmtree(self.workspace)
        self.workspace.mkdir()
        self.git("config", "--local", "commit.gpgsign", "true", cwd=self.start)
        with self.assertRaisesRegex(LiveReloadError, "unsupported local config"):
            self.session()

    def test_unsupported_fsmonitor_is_rejected_before_git_status_can_run_it(
        self,
    ) -> None:
        monitor = self.start / ".git" / "malicious-fsmonitor"
        monitor.write_text(
            "#!/usr/bin/python3\n"
            "from pathlib import Path\n"
            "Path('/work/marker').write_text('executed')\n",
            encoding="utf-8",
        )
        monitor.chmod(0o755)
        self.git(
            "config",
            "--local",
            "core.fsmonitor",
            ".git/malicious-fsmonitor",
            cwd=self.start,
        )

        with self.assertRaisesRegex(LiveReloadError, "unsupported local config"):
            self.session()
        self.assertFalse((self.workspace / "marker").exists())

    def test_finish_is_single_use_and_closed_session_cannot_finish(self) -> None:
        with self.session() as session:
            run_all(session)
            with self.assertRaisesRegex(LiveReloadError, "already finalized"):
                session.finish()

        self.workspace = self.base / "work-closed"
        self.evidence = self.base / "evidence-closed"
        self.workspace.mkdir()
        self.evidence.mkdir()
        session = self.session()
        session.close()
        with self.assertRaisesRegex(LiveReloadError, "session is closed"):
            session.finish()

    def test_finish_rejects_host_tamper_without_overwriting_evidence(self) -> None:
        with self.session() as session:
            while session.next_operation_id is not None:
                session.request(session.next_operation_id)
            trace_path = self.evidence / "trace.json"
            (self.workspace / "App.tsx").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(LiveReloadError, "final App.tsx integrity"):
                session.finish()
            self.assertFalse(trace_path.exists())

    def test_finish_rechecks_phase_and_source_provenance(self) -> None:
        with self.session() as session:
            while session.next_operation_id is not None:
                session.request(session.next_operation_id)
            snapshot = self.evidence / "text" / "snapshot.json"
            snapshot.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(LiveReloadError, "phase snapshot integrity"):
                session.finish()
            self.assertFalse((self.evidence / "trace.json").exists())

        self.workspace = self.base / "work-source"
        self.evidence = self.base / "evidence-source"
        self.workspace.mkdir()
        self.evidence.mkdir()
        with self.session() as session:
            while session.next_operation_id is not None:
                session.request(session.next_operation_id)
            session.component_source_sha256 = "0" * 64
            with self.assertRaisesRegex(LiveReloadError, "component source changed"):
                session.finish()
            self.assertFalse((self.evidence / "trace.json").exists())

    def test_start_workspace_and_evidence_roots_must_not_overlap(self) -> None:
        with self.assertRaisesRegex(LiveReloadError, "must not overlap"):
            LiveReloadSession(self.chapter, self.start, self.start, self.evidence)
        with self.assertRaisesRegex(LiveReloadError, "must not overlap"):
            LiveReloadSession(self.chapter, self.start, self.workspace, self.workspace)


class SDK57LiveReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        if not os.access("/usr/bin/bwrap", os.X_OK):
            self.skipTest("NOT_READY: SDK57 execution probe needs /usr/bin/bwrap")
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.chapter = SDK57_CANDIDATE / "chapter-live-reload.md"
        self.start = self.base / "start"
        shutil.copytree(SDK57_CANDIDATE / "start-source", self.start)
        self.git("init", cwd=self.start)
        self.git("config", "--local", "user.name", "G6 Fixture", cwd=self.start)
        self.git(
            "config", "--local", "user.email", "g6@example.invalid", cwd=self.start
        )
        self.git("add", ".", cwd=self.start)
        self.git("commit", "-m", "最初の画面を作る", cwd=self.start)
        self.workspace = self.base / "work"
        self.evidence = self.base / "evidence"
        self.workspace.mkdir()
        self.evidence.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str, cwd: Path) -> str:
        result = subprocess.run(
            ["/usr/bin/git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin", "HOME": str(self.base / "host-home")},
        )
        return result.stdout

    def session(self) -> LiveReloadSession:
        return LiveReloadSession(
            self.chapter,
            self.start,
            self.workspace,
            self.evidence,
            profile=SDK57_PROFILE,
        )

    def test_sdk57_executes_full_source_app_only_commit_and_restore(self) -> None:
        with self.session() as session:
            receipt = run_all(session)
        trace = receipt["trace"]
        self.assertEqual(SDK57_PROFILE, trace["profile"])
        self.assertEqual(14, len(trace["start_source_files"]))
        self.assertEqual(14, len(trace["final_source_files"]))
        self.assertEqual(13, len(trace["actions"]))
        self.assertEqual(
            ["complete-edit", "committed", "restore-practice-dirty", "git-restored"],
            [action["phase"] for action in trace["actions"] if action["phase"]],
        )
        self.assertEqual(
            ["App.tsx"],
            self.git(
                "diff",
                "--name-only",
                trace["start_head"],
                trace["final_head"],
                cwd=self.workspace,
            ).splitlines(),
        )
        start_hashes = {
            item["path"]: item["sha256"] for item in trace["start_source_files"]
        }
        final_hashes = {
            item["path"]: item["sha256"] for item in trace["final_source_files"]
        }
        self.assertEqual(
            {
                path: digest
                for path, digest in start_hashes.items()
                if path != "App.tsx"
            },
            {
                path: digest
                for path, digest in final_hashes.items()
                if path != "App.tsx"
            },
        )
        self.assertNotEqual(start_hashes["App.tsx"], final_hashes["App.tsx"])
        self.assertEqual("", self.git("status", "--porcelain", cwd=self.workspace))

    def test_sdk57_finish_rejects_non_app_source_mutation(self) -> None:
        with self.session() as session:
            while session.next_operation_id is not None:
                session.request(session.next_operation_id)
            (self.workspace / "package.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(
                LiveReloadError, "start source hash mismatch: package.json"
            ):
                session.finish()
            self.assertFalse((self.evidence / "trace.json").exists())

    def test_sdk57_start_requires_all_normal_tracked_files(self) -> None:
        self.git("update-index", "--skip-worktree", "package.json", cwd=self.start)
        with self.assertRaisesRegex(LiveReloadError, "normal Git index flags"):
            self.session()


if __name__ == "__main__":
    unittest.main()
