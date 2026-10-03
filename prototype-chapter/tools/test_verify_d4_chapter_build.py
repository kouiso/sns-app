from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from verify_d4_chapter_build import BuildVerificationError, reconstruct_from_chapter


class ChapterBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.source = Path(__file__).resolve().parents[1] / "candidates/d4-runtime"
        manifest = json.loads((cls.source / "start-manifest.json").read_text())
        for relative in ["chapter-build.md", "start-manifest.json"] + ["start/" + e["path"] for e in manifest["files"]]:
            destination = cls.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cls.source / relative, destination)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def assert_rejected_change(self, relative, transform):
        path = self.root / relative
        original = path.read_bytes()
        try:
            changed = transform(original)
            self.assertNotEqual(changed, original, "negative fixture must actually mutate source")
            path.write_bytes(changed)
            with self.assertRaises(BuildVerificationError):
                reconstruct_from_chapter(self.root)
        finally:
            path.write_bytes(original)

    def test_disclosed_listing_build_changes_only_app_and_adds_component(self):
        files, receipt = reconstruct_from_chapter(self.root)
        self.assertEqual(len(files), 20)
        self.assertEqual(receipt["changed_paths"], ["App.tsx", "components/RlsTrial.tsx"])
        self.assertFalse(receipt["model_or_UI_run"])
        for path, content in files.items():
            if path not in receipt["changed_paths"]:
                self.assertEqual(content, (self.root / "start" / path).read_bytes())
        self.assertIn(b"<RlsTrial key={userId}", files["App.tsx"])
        self.assertEqual(hashlib.sha256(files["components/RlsTrial.tsx"]).hexdigest(), receipt["component_sha256"])

    def test_corrupted_or_missing_listing_is_rejected(self):
        self.assert_rejected_change("chapter-build.md", lambda b: b.replace(b"### "+"コード 2".encode(), b"### "+"コード 1".encode(), 1))
        self.assert_rejected_change("chapter-build.md", lambda b: b.replace(b"15_000", b"50_000", 1))

    def test_modified_start_cannot_be_silently_backfilled(self):
        self.assert_rejected_change("start/App.tsx", lambda b: b + b"\n// RlsTrial\n")
        self.assert_rejected_change("start-manifest.json", lambda b: b.replace(b"9d6d5087", b"0d6d5087", 1))

    def test_undeclared_file_or_symlink_is_rejected(self):
        path = self.root / "start" / ".env"
        try:
            path.write_text("undeclared fixture")
            with self.assertRaises(BuildVerificationError):
                reconstruct_from_chapter(self.root)
        finally:
            path.unlink()
        try:
            path.symlink_to(self.root / "start" / "App.tsx")
            with self.assertRaises(BuildVerificationError):
                reconstruct_from_chapter(self.root)
        finally:
            path.unlink()

    def test_reviewed_new_chapter_still_requires_exact_hookup(self):
        path = self.root / "chapter-build.md"
        original = path.read_bytes()
        changed = original.replace(b"? <RlsTrial key={userId}", b"? <OtherTrial key={userId}", 1)
        self.assertNotEqual(changed, original)
        try:
            path.write_bytes(changed)
            with mock.patch("verify_d4_chapter_build.EXPECTED_CHAPTER_SHA256", hashlib.sha256(changed).hexdigest()):
                with self.assertRaisesRegex(BuildVerificationError, "unreviewed UI hookup"):
                    reconstruct_from_chapter(self.root)
        finally:
            path.write_bytes(original)

    def test_declared_source_symlink_fails_with_public_error_type(self):
        path = self.root / "start" / "App.tsx"
        original = path.read_bytes()
        try:
            path.unlink()
            path.symlink_to(self.root / "start" / "README.md")
            with self.assertRaises(BuildVerificationError):
                reconstruct_from_chapter(self.root)
        finally:
            path.unlink()
            path.write_bytes(original)

    def test_special_node_and_empty_target_directory_are_rejected(self):
        fifo = self.root / "start" / "unexpected"
        try:
            os.mkfifo(fifo)
            with self.assertRaises(BuildVerificationError):
                reconstruct_from_chapter(self.root)
        finally:
            fifo.unlink()
        directory = self.root / "start" / "components"
        try:
            directory.mkdir()
            with self.assertRaises(BuildVerificationError):
                reconstruct_from_chapter(self.root)
        finally:
            directory.rmdir()

    def test_unmounted_ui_and_false_formal_claim_are_rejected(self):
        self.assert_rejected_change("chapter-build.md", lambda b: b.replace(
            b"userId\n  ? <RlsTrial key={userId} client={client} userId={userId} />\n  : " + '<Text style={styles.body}>ログイン状態をもう一度確認してください。</Text>'.encode(),
            '<Text style={styles.body}>投稿画面は接続しません。</Text>'.encode(), 1))
        self.assert_rejected_change("chapter-build.md", lambda b: b.replace(
            "正式D4/G6の合格は未測定".encode(), "正式A5/D4/G6は合格済み".encode(), 1))

    def test_manifest_cannot_claim_formal_start_or_add_untrusted_fields(self):
        for key, value in [("formal_start_frozen", True), ("contains_rls_trial", True),
                           ("version", True), ("scope", "FORMAL_PASS"), ("private", "undeclared")]:
            def change(raw, key=key, value=value):
                doc = json.loads(raw)
                doc[key] = value
                return json.dumps(doc).encode()
            self.assert_rejected_change("start-manifest.json", change)
        self.assert_rejected_change("start-manifest.json", lambda b: b.replace(
            b'"version": 1,', b'"version": 1, "version": 1,', 1))

    def test_hookup_target_cannot_match_zero_or_multiple_times(self):
        self.assert_rejected_change("chapter-build.md", lambda b: b.replace("SNS のプロフィール機能は次の実装範囲です。".encode(), b"wrong target", 1))


if __name__ == "__main__":
    unittest.main()
