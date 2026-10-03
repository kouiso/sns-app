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

OLD_HOOKUP = (
    "          ) : (\n"
    "            <Text style={styles.body}>メール確認済みのセッションです。"
    "SNS のプロフィール機能は次の実装範囲です。</Text>\n"
    "          )}"
).encode()
NEW_HOOKUP = (
    "          ) : (\n"
    "            userId\n"
    "              ? <RlsTrial key={userId} client={client} userId={userId} />\n"
    "              : <Text style={styles.body}>ログイン状態をもう一度確認してください。</Text>\n"
    "          )}"
).encode()
HOOKUP_START = "## サインイン後の画面につなぐ\n".encode()
HOOKUP_END = "## 型を検査する\n".encode()


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

    def assert_rejected_reviewed_chapter(self, transform, message):
        path = self.root / "chapter-build.md"
        original = path.read_bytes()
        try:
            changed = transform(original)
            self.assertNotEqual(changed, original, "negative fixture must actually mutate chapter")
            path.write_bytes(changed)
            reviewed_hash = hashlib.sha256(changed).hexdigest()
            with mock.patch("verify_d4_chapter_build.EXPECTED_CHAPTER_SHA256", reviewed_hash):
                with self.assertRaisesRegex(BuildVerificationError, message):
                    reconstruct_from_chapter(self.root)
        finally:
            path.write_bytes(original)

    def test_disclosed_listing_build_changes_only_app_and_adds_component(self):
        files, receipt = reconstruct_from_chapter(self.root)
        self.assertEqual(len(files), 20)
        self.assertEqual(receipt["changed_paths"], ["App.tsx", "components/RlsTrial.tsx"])
        self.assertEqual(receipt["chapter_sha256"], "93145b45bf929d867bbcee35b022d83e521510f9b54c4f31f0400f24fa340d37")
        self.assertEqual(receipt["final_snapshot_sha256"], "681aea8e3273ff1197cc51136e7db6f819711b0178773cd328201ded50f37024")
        self.assertFalse(receipt["model_or_UI_run"])
        for path, content in files.items():
            if path not in receipt["changed_paths"]:
                self.assertEqual(content, (self.root / "start" / path).read_bytes())
        self.assertIn(b"<RlsTrial key={userId}", files["App.tsx"])
        self.assertIn(b'testID="new-password-input"', files["App.tsx"])
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
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(b"? <RlsTrial key={userId}", b"? <OtherTrial key={userId}", 1),
            "unreviewed UI hookup",
        )

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
            b"? <RlsTrial key={userId} client={client} userId={userId} />",
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
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(OLD_HOOKUP, OLD_HOOKUP.replace(
                "SNS のプロフィール機能は次の実装範囲です。".encode(), b"wrong target"), 1),
            "unreviewed UI hookup",
        )

    def test_recovery_wrapper_and_extra_hookup_snippet_are_rejected(self):
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(NEW_HOOKUP, NEW_HOOKUP.replace(b"          ) : (", b"          ) && (", 1), 1),
            "unreviewed UI hookup",
        )
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(
                "\n## 型を検査する\n".encode(),
                "\n```tsx\n<Text>extra hookup</Text>\n```\n\n## 型を検査する\n".encode(),
                1,
            ),
            "hookup requires import, old, new snippets",
        )

    def test_hookup_section_headings_must_be_unique_present_and_ordered(self):
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(HOOKUP_START, b"## missing hookup start\n", 1),
            "hookup section headings missing or duplicated",
        )
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(HOOKUP_END, b"## missing hookup end\n", 1),
            "hookup section headings missing or duplicated",
        )
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(HOOKUP_START, HOOKUP_START + HOOKUP_START, 1),
            "hookup section headings missing or duplicated",
        )
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(HOOKUP_END, HOOKUP_END + HOOKUP_END, 1),
            "hookup section headings missing or duplicated",
        )
        self.assert_rejected_reviewed_chapter(
            lambda b: b.replace(HOOKUP_START, b"## temporary hookup heading\n", 1)
            .replace(HOOKUP_END, HOOKUP_START, 1)
            .replace(b"## temporary hookup heading\n", HOOKUP_END, 1),
            "hookup section headings reordered",
        )


if __name__ == "__main__":
    unittest.main()
