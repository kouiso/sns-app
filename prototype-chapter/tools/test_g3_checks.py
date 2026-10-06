#!/usr/bin/env python3
"""g3_checks.py の正例・負例。"""

from __future__ import annotations

import json
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from g3_checks import (
    check_chapter,
    infer_chapter_id,
    is_contrast,
    load_start_state_manifest,
    policy_findings,
    structural_findings,
)


GOOD_CHAPTER = """# 章

磯貝「最初の説明です。次を確かめます」

阿部「分かりました」

```tsx
export const value = 1;
```
"""


class G3ChecksTest(unittest.TestCase):
    def test_structure_accepts_25_code_lines_and_three_sentences(self) -> None:
        code = "\n".join(f"line{i}" for i in range(25))
        text = f"一文目です。二文目です。三文目です。\n\n```ts\n{code}\n```\n"
        self.assertEqual([], structural_findings(Path("ok.md"), text))

    def test_structure_rejects_26_code_lines(self) -> None:
        code = "\n".join(f"line{i}" for i in range(26))
        findings = structural_findings(Path("bad.md"), f"```ts\n{code}\n```\n")
        self.assertEqual(
            ["structure/code-lines"], [finding.check for finding in findings]
        )

    def test_structure_rejects_four_sentence_paragraph(self) -> None:
        findings = structural_findings(Path("bad.md"), "一文。二文。三文。四文。\n")
        self.assertEqual(
            ["structure/paragraph-sentences"], [finding.check for finding in findings]
        )

    def test_structure_rejects_four_sentence_list_item(self) -> None:
        findings = structural_findings(Path("bad.md"), "- 一文。二文。三文。四文。\n")
        self.assertEqual(
            ["structure/paragraph-sentences"], [finding.check for finding in findings]
        )

    def test_structure_rejects_26_line_blockquote_fence(self) -> None:
        code = "\n".join(f"> line{i}" for i in range(26))
        findings = structural_findings(Path("bad.md"), f"> ```tsx\n{code}\n> ```\n")
        self.assertEqual(
            ["structure/code-lines"], [finding.check for finding in findings]
        )

    def test_structure_rejects_short_unclosed_fence(self) -> None:
        findings = structural_findings(Path("bad.md"), "```ts\nconst value = 1;\n")
        self.assertEqual(
            ["structure/unclosed-fence"], [finding.check for finding in findings]
        )

    def test_policy_allows_historical_explanation(self) -> None:
        text = "NestJS と Redis は旧構成で不採用になりました。Xcode も学習者には要求しません。\n"
        self.assertEqual([], policy_findings(Path("history.md"), text))

    def test_policy_rejects_disallowed_stack_usage_in_code(self) -> None:
        text = "```ts\nimport { PrismaClient } from '@prisma/client';\n```\n"
        findings = policy_findings(Path("bad.md"), text)
        self.assertEqual(
            ["policy/disallowed-stack"], [finding.check for finding in findings]
        )

    def test_policy_rejects_adoption_instruction_but_not_name_alone(self) -> None:
        findings = policy_findings(Path("bad.md"), "この章では NestJS を使います。\n")
        self.assertEqual(
            ["policy/disallowed-stack"], [finding.check for finding in findings]
        )

    def test_policy_rejects_adoption_split_across_visible_lines(self) -> None:
        findings = policy_findings(Path("bad.md"), "この章では NestJS を\n使います。\n")
        self.assertEqual(
            ["policy/disallowed-stack"], [finding.check for finding in findings]
        )

    def test_policy_rejects_unknown_speaker(self) -> None:
        findings = policy_findings(Path("bad.md"), "田中「始めます」\n")
        self.assertEqual(["policy/speaker"], [finding.check for finding in findings])

    def test_policy_does_not_treat_prose_before_quote_as_speaker(self) -> None:
        text = "最後まで進むと、手元の端末に「はじめての画面」という文字が出ます。\n"
        self.assertEqual([], policy_findings(Path("ok.md"), text))

    def test_policy_does_not_treat_short_prose_before_quote_as_speaker(self) -> None:
        text = "手元の端末に「はじめての画面」という文字を出します。\n"
        self.assertEqual([], policy_findings(Path("ok.md"), text))

    def test_policy_rejects_distribution_contradiction(self) -> None:
        findings = policy_findings(Path("bad.md"), "教材本文の正本は EPUB です。\n")
        self.assertEqual(
            ["policy/distribution"], [finding.check for finding in findings]
        )

    def test_policy_rejects_distribution_split_across_visible_lines(self) -> None:
        findings = policy_findings(Path("bad.md"), "教材本文の正本は\nEPUB です。\n")
        self.assertEqual(
            ["policy/distribution"], [finding.check for finding in findings]
        )

    def test_policy_ignores_html_comment(self) -> None:
        self.assertEqual(
            [], policy_findings(Path("ok.md"), "<!-- NestJS を使います。 -->\n")
        )

    def test_full_checks_require_manifest_and_dev_log_for_real_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "sample.md"
            chapter.write_text(GOOD_CHAPTER, encoding="utf-8")
            findings = check_chapter(chapter, root / "dev-logs", None)
        self.assertEqual(
            {"start-state/definition", "dev-log/existence"},
            {finding.check for finding in findings},
        )

    def test_manifest_definition_cannot_be_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "sample.md"
            chapter.write_text(GOOD_CHAPTER, encoding="utf-8")
            logs = root / "dev-logs"
            logs.mkdir()
            (logs / "sample.md").write_text("record\n", encoding="utf-8")
            findings = check_chapter(
                chapter,
                logs,
                {
                    "sample": {
                        "snapshot": {
                            "revision": "test",
                            "source_root": "declared-empty",
                            "status": "declared-empty-trial",
                            "tracked_files": [],
                            "allow_empty": True,
                        },
                        "allowed_state_contract": "空の開始状態",
                        "forbidden_paths": [],
                        "forbidden_patterns": [],
                    }
                },
            )
        self.assertEqual(
            ["start-state/definition"], [finding.check for finding in findings]
        )

    def test_manifest_detects_mixed_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "sample.md"
            chapter.write_text(
                GOOD_CHAPTER + "app/finished.tsx を開きます。\n", encoding="utf-8"
            )
            source = root / "starter"
            source.mkdir()
            (source / "app").mkdir()
            (source / "app" / "finished.tsx").write_text(
                "export const done = true;\n", encoding="utf-8"
            )
            logs = root / "dev-logs"
            logs.mkdir()
            (logs / "sample.md").write_text("record\n", encoding="utf-8")
            findings = check_chapter(
                chapter,
                logs,
                {
                    "sample": {
                        "snapshot": {
                            "revision": "test",
                            "source_root": "starter",
                            "status": "unfrozen-reference-candidate",
                            "tracked_files": [
                                {"path": "app/finished.tsx", "sha256": "a" * 64}
                            ],
                        },
                        "allowed_state_contract": "空の開始状態",
                        "forbidden_paths": ["app/finished.tsx"],
                        "forbidden_patterns": [],
                    }
                },
                root,
            )
        self.assertEqual(
            ["start-state/mixed-content"], [finding.check for finding in findings]
        )

    def test_manifest_detects_forbidden_pattern_in_start_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "sample.md"
            chapter.write_text(GOOD_CHAPTER, encoding="utf-8")
            starter = root / "starter"
            starter.mkdir()
            (starter / "App.tsx").write_text(
                "const client = createClient(url, key);\n", encoding="utf-8"
            )
            logs = root / "dev-logs"
            logs.mkdir()
            (logs / "sample.md").write_text("record\n", encoding="utf-8")
            findings = check_chapter(
                chapter,
                logs,
                {
                    "sample": {
                        "snapshot": {
                            "revision": "test",
                            "source_root": "starter",
                            "status": "unfrozen-reference-candidate",
                            "tracked_files": [{"path": "App.tsx", "sha256": "a" * 64}],
                        },
                        "allowed_state_contract": "最初の画面だけ",
                        "forbidden_paths": ["supabase"],
                        "forbidden_patterns": [r"createClient\s*\("],
                    }
                },
                root,
            )
        self.assertEqual(
            ["start-state/mixed-content"], [finding.check for finding in findings]
        )

    def test_generated_package_lock_is_not_scanned_as_source_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "sample.md"
            chapter.write_text(GOOD_CHAPTER, encoding="utf-8")
            starter = root / "starter"
            starter.mkdir()
            (starter / "package-lock.json").write_text(
                '{"peer":"expo-router"}\n', encoding="utf-8"
            )
            logs = root / "dev-logs"
            logs.mkdir()
            (logs / "sample.md").write_text("record\n", encoding="utf-8")
            findings = check_chapter(
                chapter,
                logs,
                {
                    "sample": {
                        "snapshot": {
                            "revision": "test",
                            "source_root": "starter",
                            "status": "unfrozen-reference-candidate",
                            "tracked_files": [
                                {"path": "package-lock.json", "sha256": "a" * 64}
                            ],
                        },
                        "allowed_state_contract": "生成lockfileだけ",
                        "forbidden_paths": ["app"],
                        "forbidden_patterns": [r"expo-router"],
                    }
                },
                root,
            )
        self.assertEqual([], findings)

    def test_plain_and_minus_only_skip_manifest_and_dev_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ("chapter-sample-plain.md", "chapter-sample-minus.md"):
                chapter = root / filename
                chapter.write_text(GOOD_CHAPTER, encoding="utf-8")
                self.assertTrue(is_contrast(chapter))
                self.assertEqual([], check_chapter(chapter, root / "missing", None))
            ordinary = root / "sample-draft.md"
            ordinary.write_text(GOOD_CHAPTER, encoding="utf-8")
            self.assertFalse(is_contrast(ordinary))
            self.assertTrue(check_chapter(ordinary, root / "missing", None))

            ordinary_with_plain_suffix = root / "sample-plain.md"
            ordinary_with_plain_suffix.write_text(GOOD_CHAPTER, encoding="utf-8")
            self.assertFalse(is_contrast(ordinary_with_plain_suffix))
            self.assertTrue(
                check_chapter(ordinary_with_plain_suffix, root / "missing", None)
            )

    def test_g6_directory_names_supply_chapter_id(self) -> None:
        self.assertEqual("auth-login", infer_chapter_id(Path("g6/auth-login/plain.md")))
        self.assertEqual(
            "auth-login", infer_chapter_id(Path("chapter-auth-login-minus.md"))
        )

    def test_load_manifest_rejects_missing_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps({"version": 1}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "chapters"):
                load_start_state_manifest(path)

    def test_load_manifest_requires_snapshot_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "scope": "chapter-content-mixing-only",
                        "snapshot_conformance_checked": False,
                        "chapters": {
                            "sample": {
                                "allowed_state_contract": "空の開始状態",
                                "forbidden_paths": ["future.ts"],
                                "forbidden_patterns": [],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "snapshot"):
                load_start_state_manifest(path)

    def test_load_manifest_accepts_explicit_snapshot_and_forbidden_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "scope": "chapter-content-mixing-only",
                        "snapshot_conformance_checked": False,
                        "chapters": {
                            "sample": {
                                "snapshot": {
                                    "revision": "chapter/previous",
                                    "source_root": "starter",
                                    "status": "unfrozen-reference-candidate",
                                    "tracked_files": [
                                        {"path": "App.tsx", "sha256": "a" * 64}
                                    ],
                                },
                                "allowed_state_contract": "前章末の App.tsx だけを持つ",
                                "forbidden_paths": ["app/future.tsx"],
                                "forbidden_patterns": [],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_start_state_manifest(path)
        self.assertIn("sample", loaded)

    def test_full_shell_entry_passes_with_explicit_inputs(self) -> None:
        tools_dir = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "sample.md"
            chapter.write_text(GOOD_CHAPTER, encoding="utf-8")
            starter = root / "starter"
            starter.mkdir()
            (starter / "App.tsx").write_text(
                "export const start = true;\n", encoding="utf-8"
            )
            starter_hash = hashlib.sha256(
                (starter / "App.tsx").read_bytes()
            ).hexdigest()
            logs = root / "dev-logs"
            logs.mkdir()
            (logs / "sample.md").write_text("record\n", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "scope": "chapter-content-mixing-only",
                        "snapshot_conformance_checked": False,
                        "chapters": {
                            "sample": {
                                "snapshot": {
                                    "revision": "chapter/previous",
                                    "source_root": "starter",
                                    "status": "unfrozen-reference-candidate",
                                    "tracked_files": [
                                        {"path": "App.tsx", "sha256": starter_hash}
                                    ],
                                },
                                "allowed_state_contract": "前章末の App.tsx だけを持つ",
                                "forbidden_paths": ["app/future.tsx"],
                                "forbidden_patterns": [],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(tools_dir / "g3-full.sh"),
                    "--start-state-manifest",
                    str(manifest),
                    "--dev-logs-dir",
                    str(logs),
                    str(chapter),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=tools_dir.parent,
            )
        diagnostic = "\n".join(
            part for part in (result.stdout, result.stderr) if part.strip()
        )
        self.assertEqual(0, result.returncode, diagnostic)
        self.assertIn("正式 G3 通過証拠ではない", result.stdout)

    def test_load_manifest_rejects_duplicate_json_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                '{"version":1,"version":1,"scope":"chapter-content-mixing-only",'
                '"snapshot_conformance_checked":false,"chapters":{}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "重複キー"):
                load_start_state_manifest(path)

    def test_load_manifest_rejects_boolean_version_and_nonstandard_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                '{"version":true,"scope":"chapter-content-mixing-only",'
                '"snapshot_conformance_checked":false,"chapters":{}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "version=1"):
                load_start_state_manifest(path)

            path.write_text(
                '{"version":NaN,"scope":"chapter-content-mixing-only",'
                '"snapshot_conformance_checked":false,"chapters":{}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "非標準"):
                load_start_state_manifest(path)

    def test_start_source_root_symlink_cannot_escape_manifest_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_root = root / "manifest"
            manifest_root.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (outside / "App.tsx").write_text(
                "const client = createClient(url, key);\n", encoding="utf-8"
            )
            (manifest_root / "starter").symlink_to(outside, target_is_directory=True)
            chapter = root / "sample.md"
            chapter.write_text(GOOD_CHAPTER, encoding="utf-8")
            logs = root / "dev-logs"
            logs.mkdir()
            (logs / "sample.md").write_text("record\n", encoding="utf-8")
            findings = check_chapter(
                chapter,
                logs,
                {
                    "sample": {
                        "snapshot": {
                            "revision": "test",
                            "source_root": "starter",
                            "status": "unfrozen-reference-candidate",
                            "tracked_files": [{"path": "App.tsx", "sha256": "a" * 64}],
                        },
                        "allowed_state_contract": "試作用",
                        "forbidden_paths": ["supabase"],
                        "forbidden_patterns": [r"createClient\s*\("],
                    }
                },
                manifest_root,
            )
        self.assertEqual(
            ["start-state/source-input"], [item.check for item in findings]
        )

    def test_load_manifest_accepts_escaped_regex(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "scope": "chapter-content-mixing-only",
                        "snapshot_conformance_checked": False,
                        "chapters": {
                            "sample": {
                                "snapshot": {
                                    "revision": "trial",
                                    "source_root": "declared-empty",
                                    "status": "declared-empty-trial",
                                    "tracked_files": [],
                                    "allow_empty": True,
                                },
                                "allowed_state_contract": "空の開始状態",
                                "forbidden_paths": [],
                                "forbidden_patterns": [r"auth\.uid\(\)"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_start_state_manifest(path)
        self.assertEqual([r"auth\.uid\(\)"], loaded["sample"]["forbidden_patterns"])

    def test_load_manifest_rejects_unsafe_posix_paths(self) -> None:
        for unsafe in (r"..\App.tsx", ".", "../App.tsx", "/App.tsx", "file://App.tsx"):
            with (
                self.subTest(unsafe=unsafe),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "manifest.json"
                path.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "scope": "chapter-content-mixing-only",
                            "snapshot_conformance_checked": False,
                            "chapters": {
                                "sample": {
                                    "snapshot": {
                                        "revision": "trial",
                                        "source_root": "starter",
                                        "status": "unfrozen-reference-candidate",
                                        "tracked_files": [
                                            {"path": unsafe, "sha256": "a" * 64}
                                        ],
                                    },
                                    "allowed_state_contract": "試作用",
                                    "forbidden_paths": ["future.ts"],
                                    "forbidden_patterns": [],
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "path が不正"):
                    load_start_state_manifest(path)

    def test_load_manifest_rejects_unknown_nested_keys(self) -> None:
        for location in ("entry", "snapshot", "tracked"):
            with (
                self.subTest(location=location),
                tempfile.TemporaryDirectory() as directory,
            ):
                entry: dict[str, object] = {
                    "snapshot": {
                        "revision": "trial",
                        "source_root": "starter",
                        "status": "unfrozen-reference-candidate",
                        "tracked_files": [{"path": "App.tsx", "sha256": "a" * 64}],
                    },
                    "allowed_state_contract": "試作用",
                    "forbidden_paths": ["future.ts"],
                    "forbidden_patterns": [],
                }
                if location == "entry":
                    entry["unknown"] = True
                elif location == "snapshot":
                    snapshot = entry["snapshot"]
                    assert isinstance(snapshot, dict)
                    snapshot["unknown"] = True
                else:
                    snapshot = entry["snapshot"]
                    assert isinstance(snapshot, dict)
                    tracked = snapshot["tracked_files"]
                    assert isinstance(tracked, list)
                    tracked[0]["unknown"] = True
                path = Path(directory) / "manifest.json"
                path.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "scope": "chapter-content-mixing-only",
                            "snapshot_conformance_checked": False,
                            "chapters": {"sample": entry},
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "未定義キー|キーの過不足"):
                    load_start_state_manifest(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
