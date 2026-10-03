from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from g6_live_reload import (
    COMMIT_MESSAGE,
    FINAL_APP_SHA256,
    LiveReloadError,
    LiveReloadSession,
    RESTORE_PRACTICE_TEXT,
    run_all,
)


TOOLS = Path(__file__).resolve().parent
PROTOTYPE = TOOLS.parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
        self.git("config", "--local", "user.email", "g6@example.invalid", cwd=self.start)
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
        return LiveReloadSession(self.chapter, self.start, self.workspace, self.evidence)

    def test_real_bwrap_executes_fixed_app_git_and_restore_stages(self) -> None:
        with self.session() as session:
            receipt = run_all(session)
        self.assertEqual(FINAL_APP_SHA256, sha((self.workspace / "App.tsx").read_bytes()))
        self.assertEqual("", self.git("status", "--porcelain", cwd=self.workspace))
        self.assertEqual(
            COMMIT_MESSAGE,
            self.git("log", "-1", "--pretty=%s", cwd=self.workspace).strip(),
        )
        self.assertEqual(
            ["App.tsx"],
            self.git("show", "--pretty=", "--name-only", "HEAD", cwd=self.workspace)
            .splitlines(),
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
        for claim in ("formal_g6_exec", "model_mcp_connected", "metro_executed", "ui_validated"):
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
            with self.assertRaisesRegex(LiveReloadError, "order violation"):
                session.request("write-note-style")
            session.request("write-app-function")
            with self.assertRaisesRegex(LiveReloadError, "order violation"):
                session.request("write-app-function")

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
            with self.assertRaisesRegex(LiveReloadError, "did not show App.tsx modified"):
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

    def test_executable_git_hook_and_unsupported_local_config_are_rejected(self) -> None:
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

    def test_unsupported_fsmonitor_is_rejected_before_git_status_can_run_it(self) -> None:
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
            LiveReloadSession(
                self.chapter, self.start, self.workspace, self.workspace
            )


if __name__ == "__main__":
    unittest.main()
