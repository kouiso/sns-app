"""Mutations must not turn candidate integrity into formal approval."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from verify_sdk57_candidate import CandidateError, validate

ROOT = Path(__file__).resolve().parents[1] / "candidates" / "sdk57"


class CandidateTests(unittest.TestCase):
    temporary: ClassVar[tempfile.TemporaryDirectory[str]]
    candidate: ClassVar[Path]
    baseline: ClassVar[dict[str, bytes]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="sdk57-integrity-")
        cls.candidate = Path(cls.temporary.name) / "candidate"
        cls.baseline = {
            path.relative_to(ROOT).as_posix(): path.read_bytes()
            for path in ROOT.rglob("*")
            if path.is_file()
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def setUp(self) -> None:
        if self.candidate.exists():
            shutil.rmtree(self.candidate)
        self.candidate.mkdir()
        for name, content in self.baseline.items():
            path = self.candidate / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def manifest(self) -> dict:
        return json.loads((self.candidate / "candidate-manifest.json").read_text())

    def write_manifest(self, value: dict) -> None:
        (self.candidate / "candidate-manifest.json").write_text(json.dumps(value))

    def test_real_candidate_integrity(self) -> None:
        result = validate(self.candidate)
        self.assertEqual(result["status"], "INTEGRITY_COMPONENT_PASS")
        self.assertIs(result["formal_g6"], False)
        self.assertEqual(result["shared_start_file_count"], 14)

    def test_modified_file_rejected(self) -> None:
        path = self.candidate / "start-source/App.tsx"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(CandidateError, "hash mismatch"):
            validate(self.candidate)

    def test_self_consistent_forged_starter_rejected(self) -> None:
        path = self.candidate / "start-source/index.ts"
        path.write_bytes(path.read_bytes() + b"\n")
        manifest = self.manifest()
        forged = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["file_sha256"]["start-source/index.ts"] = forged
        manifest["shared_start_source"]["files"]["start-source/index.ts"] = forged
        self.write_manifest(manifest)
        with self.assertRaisesRegex(CandidateError, "reviewed 14-file"):
            validate(self.candidate)

    def test_extra_file_and_empty_directory_rejected(self) -> None:
        for name, directory in (("unexpected", False), ("empty", True)):
            with self.subTest(name=name):
                path = self.candidate / name
                path.mkdir() if directory else path.write_text("x")
                with self.assertRaises(CandidateError):
                    validate(self.candidate)
                path.rmdir() if directory else path.unlink()

    def test_missing_starter_rejected(self) -> None:
        (self.candidate / "start-source/LICENSE").unlink()
        with self.assertRaises(CandidateError):
            validate(self.candidate)

    def test_self_consistent_control_change_rejected(self) -> None:
        name = "controls/live-reload/plain.md"
        path = self.candidate / name
        path.write_text(
            path.read_text().replace("git restore App.tsx", "git reset --hard")
        )
        manifest = self.manifest()
        manifest["file_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_manifest(manifest)
        with self.assertRaisesRegex(CandidateError, "non-dialogue"):
            validate(self.candidate)

    def test_self_consistent_extra_file_rejected(self) -> None:
        path = self.candidate / ".env"
        path.write_text("private=value")
        manifest = self.manifest()
        manifest["file_sha256"][".env"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_manifest(manifest)
        with self.assertRaisesRegex(CandidateError, "reviewed layout"):
            validate(self.candidate)

    def test_symlink_file_directory_and_manifest_rejected(self) -> None:
        for name, target in (("link", "README.md"), ("link-dir", "start-source")):
            path = self.candidate / name
            path.symlink_to(self.candidate / target)
            with self.assertRaises(CandidateError):
                validate(self.candidate)
            path.unlink()
        manifest = self.candidate / "candidate-manifest.json"
        outside = self.candidate.parent / "manifest.json"
        outside.write_bytes(manifest.read_bytes())
        manifest.unlink()
        manifest.symlink_to(outside)
        with self.assertRaises(CandidateError):
            validate(self.candidate)

    def test_claim_true_and_numeric_false_rejected(self) -> None:
        original = self.manifest()
        for value in (True, 0, None):
            with self.subTest(value=value):
                manifest = json.loads(json.dumps(original))
                manifest["claims"]["g6_passed"] = value
                self.write_manifest(manifest)
                with self.assertRaises(CandidateError):
                    validate(self.candidate)

    def test_unsafe_paths_rejected_before_read(self) -> None:
        original = self.manifest()
        for name in ("../escape", "/absolute", "start-source\\App.tsx", "./README.md"):
            with self.subTest(name=name):
                manifest = json.loads(json.dumps(original))
                manifest["file_sha256"][name] = "0" * 64
                self.write_manifest(manifest)
                with self.assertRaisesRegex(CandidateError, "unsafe"):
                    validate(self.candidate)

    def test_duplicate_and_nonfinite_json_rejected(self) -> None:
        path = self.candidate / "candidate-manifest.json"
        for content in ('{"version":1,"version":1}', '{"version":NaN}'):
            path.write_text(content)
            with self.assertRaises(CandidateError):
                validate(self.candidate)

    def test_unlisted_reference_and_nonstring_hash_rejected(self) -> None:
        original = self.manifest()
        manifest = json.loads(json.dumps(original))
        manifest["chapter_entries"][0]["chapter"] = "../external.md"
        self.write_manifest(manifest)
        with self.assertRaises(CandidateError):
            validate(self.candidate)
        original["file_sha256"]["README.md"] = False
        self.write_manifest(original)
        with self.assertRaises(CandidateError):
            validate(self.candidate)


class BootstrapFlowTests(unittest.TestCase):
    """Real Markdown shell control flow; npm/Expo are local stubs, not UI proof."""

    temporary: ClassVar[tempfile.TemporaryDirectory[str]]
    directory: ClassVar[Path]
    distribution: ClassVar[Path]
    bootstrap: ClassVar[str]
    login: ClassVar[str]
    metro: ClassVar[str]
    resume: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        import re

        if shutil.which("bash") is None or shutil.which("git") is None:
            raise unittest.SkipTest("UNJUDGED: shell simulation requires Bash and Git")
        cls.temporary = tempfile.TemporaryDirectory(prefix="sdk57-shell-")
        cls.directory = Path(cls.temporary.name)
        cls.distribution = cls.directory / "distribution"
        shutil.copytree(ROOT, cls.distribution)
        body = (ROOT / "chapter-expo-first-screen.md").read_text()
        blocks = re.findall(r"```bash\n(.*?)\n```", body, re.S)
        cls.bootstrap = next(
            block for block in blocks if 'CANDIDATE_DIR="$PWD"' in block
        )
        cls.login = next(block for block in blocks if 'echo "ACCOUNT OK"' in block)
        cls.metro = next(
            block for block in blocks if "npx --no-install expo start" in block
        )
        cls.resume = next(
            block
            for block in blocks
            if "rm -f node_modules/.sns-sdk57-install-ready" in block
        )
        binary = cls.directory / "bin"
        binary.mkdir()
        scripts = {
            "npm": '#!/bin/sh\n[ "${SDK57_TEST_NPM_FAIL:-0}" = 1 ] && exit 9\nmkdir -p node_modules/.bin\nprintf "#!/bin/sh\\nexit 0\\n" > node_modules/.bin/expo\nchmod +x node_modules/.bin/expo\n',
            "cp": '#!/bin/sh\n[ "${SDK57_TEST_COPY_FAIL:-0}" = 1 ] && exit 9\nexec /usr/bin/cp "$@"\n',
            "npx": '#!/bin/sh\nprintf "%s\\n" "$*" >> "$SDK57_TEST_EVENTS"\ncase "$*" in\n*login) [ "${SDK57_TEST_LOGIN_FAIL:-0}" = 1 ] && exit 9;;\n*whoami) [ "${SDK57_TEST_LOGGED_IN:-1}" = 0 ] && exit 1; echo fixture-user;;\n*start*) echo fixture-QR;;\nesac\nexit 0\n',
        }
        for name, content in scripts.items():
            path = binary / name
            path.write_text(content)
            path.chmod(0o700)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def setUp(self) -> None:
        self.home = self.directory / "home"
        if self.home.exists():
            shutil.rmtree(self.home)
        self.home.mkdir()
        self.events = self.directory / "events.txt"
        self.events.unlink(missing_ok=True)
        self.project = self.home / "sns-course-work" / "my-sns-sdk57"

    def run_block(
        self,
        block: str,
        *,
        missing_distribution: bool = False,
        variables: dict[str, str] | None = None,
    ) -> str:
        import subprocess

        environment = {
            "PATH": str(self.directory / "bin") + ":/usr/bin:/bin",
            "HOME": str(self.home),
            "LANG": "C.UTF-8",
            "SDK57_TEST_EVENTS": str(self.events),
        }
        environment.update(variables or {})
        empty = self.directory / "empty"
        empty.mkdir(exist_ok=True)
        result = subprocess.run(
            [shutil.which("bash") or "/bin/bash", "-c", block],
            cwd=empty if missing_distribution else self.distribution,
            env=environment,
            text=True,
            capture_output=True,
            timeout=15,
        )
        return result.stdout + result.stderr

    def assert_later_steps_blocked(self) -> None:
        before = self.events.read_text() if self.events.exists() else ""
        self.assertIn("STOP", self.run_block(self.login))
        self.assertIn("STOP", self.run_block(self.metro))
        after = self.events.read_text() if self.events.exists() else ""
        self.assertEqual(before, after)

    def test_new_terminal_resumes_from_successful_install(self) -> None:
        self.assertIn("READY", self.run_block(self.bootstrap))
        self.assertIn("ACCOUNT OK", self.run_block(self.login))
        self.assertIn("fixture-QR", self.run_block(self.metro))

    def test_missing_distribution_blocks_login_and_server(self) -> None:
        self.assertIn("STOP", self.run_block(self.bootstrap, missing_distribution=True))
        self.assert_later_steps_blocked()

    def test_parent_repo_and_existing_destination_are_preserved(self) -> None:
        import subprocess

        parent = self.home / "sns-course-work"
        parent.mkdir()
        subprocess.run(
            [shutil.which("git") or "/usr/bin/git", "init", "-q", str(parent)],
            check=True,
            capture_output=True,
        )
        self.assertIn("STOP", self.run_block(self.bootstrap))
        self.assertFalse(self.project.exists())
        self.assert_later_steps_blocked()
        shutil.rmtree(parent / ".git")
        self.project.mkdir()
        marker = self.project / "preserve.txt"
        marker.write_text("preserve")
        self.assertIn("STOP", self.run_block(self.bootstrap))
        self.assertEqual(marker.read_text(), "preserve")
        self.assert_later_steps_blocked()

    def test_copy_or_install_failure_blocks_later_commands(self) -> None:
        for flag in ("SDK57_TEST_COPY_FAIL", "SDK57_TEST_NPM_FAIL"):
            with self.subTest(flag=flag):
                if self.project.exists():
                    shutil.rmtree(self.project)
                self.assertNotIn(
                    "READY:", self.run_block(self.bootstrap, variables={flag: "1"})
                )
                self.assert_later_steps_blocked()

    def test_failed_resume_clears_old_ready_marker(self) -> None:
        self.assertIn("READY", self.run_block(self.bootstrap))
        self.assertNotIn(
            "READY:",
            self.run_block(self.resume, variables={"SDK57_TEST_NPM_FAIL": "1"}),
        )
        self.assertFalse(
            (self.project / "node_modules/.sns-sdk57-install-ready").exists()
        )
        self.assert_later_steps_blocked()
        self.assertIn("READY", self.run_block(self.resume))
        self.assertIn("ACCOUNT OK", self.run_block(self.login))

    def test_account_failure_prints_stop_and_never_starts_server(self) -> None:
        self.assertIn("READY", self.run_block(self.bootstrap))
        self.assertIn(
            "STOP", self.run_block(self.login, variables={"SDK57_TEST_LOGIN_FAIL": "1"})
        )
        self.assertIn(
            "STOP", self.run_block(self.metro, variables={"SDK57_TEST_LOGGED_IN": "0"})
        )
        self.assertNotIn("start", self.events.read_text())


if __name__ == "__main__":
    unittest.main()
