#!/usr/bin/env python3
"""章表の偽PASSと、未決を残した下書きの誤FAILを防ぐ。"""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from chapter_table import CHAPTER_COLUMNS, TRACE_COLUMNS, validate_chapter_table


def table(columns, rows):
    return "\n".join([
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
        *("| " + " | ".join(row.get(c, "") for c in columns) + " |" for row in rows),
    ])


class ChapterTableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = []
        self.traces = []
        for order, part in enumerate(("A0", "A", "B", "C", "D", "E"), 1):
            chapter = f"chapter-{part.lower()}x"
            self.rows.append(dict(zip(CHAPTER_COLUMNS, [
                chapter, str(order), part, "タイトル", "画面が動く",
                self.rows[-1]["章ID"] if self.rows else "-", "-", "未着手", "非節目",
                "SNSの画面へつながる", "screen", "文字が変わる", "-",
            ])))
            self.traces.append(dict(zip(TRACE_COLUMNS, [
                chapter, ",".join(f"FR{i}" for i in range(1, 16)) if order == 3 else "-",
                "04の画面", "05のRLS", "08の試験", "前章の知識", "evidence.md",
            ])))
        (self.root / "evidence.md").write_text("実行証拠の検証は独立レビューが担う。", encoding="utf-8")

    def document(self, extra=""):
        return "版: test-v1\n位置づけ: DRAFT / NON-G1\n\n## 章一覧\n" + table(CHAPTER_COLUMNS, self.rows) + "\n\n## 対応表\n" + table(TRACE_COLUMNS, self.traces) + "\n" + extra

    def check(self, extra=""):
        return validate_chapter_table(self.document(extra), self.root)

    def assertInvalid(self, result):
        self.assertFalse(result["draftStructureValid"], result)
        self.assertFalse(result["declaredGateInputsComplete"], result)
        self.assertTrue(result["errors"], result)

    def test_complete_declarations_are_not_gate_approval(self):
        result = self.check()
        self.assertTrue(result["draftStructureValid"], result)
        self.assertTrue(result["declaredGateInputsComplete"], result)
        self.assertEqual(result["activeChapterCount"], 6)
        self.assertEqual(result["unresolvedDependencies"], [])

    def test_valid_draft_keeps_unresolved_and_missing_evidence(self):
        self.rows[0]["未決依存"] = "B26,C8"
        self.rows[0]["節目"] = ""
        self.traces[0]["証拠"] = "-"
        result = self.check()
        self.assertTrue(result["draftStructureValid"], result)
        self.assertFalse(result["declaredGateInputsComplete"])
        self.assertEqual(result["unresolvedDependencies"], ["B26", "C8"])

    def test_empty_missing_malformed_and_fenced_tables_fail(self):
        for text in ("", "## 章一覧\n", "```md\n" + self.document() + "\n```",
                     self.document().replace("| ---", "| bad", 1),
                     self.document().replace("| タイトル |", "| タイトル | extra |", 1),
                     self.document() + "\n```unclosed"):
            with self.subTest(text=text[:40]):
                self.assertInvalid(validate_chapter_table(text, self.root))

    def test_unknown_backlog_reference_is_not_a_real_dependency(self):
        self.rows[0]["未決依存"] = "B999"
        self.assertInvalid(validate_chapter_table(self.document(), self.root, {"B26", "C8"}))

    def test_missing_or_frozen_designation_is_not_a_draft(self):
        for replacement in ("", "位置づけ: FROZEN / G1"):
            text = self.document().replace("位置づけ: DRAFT / NON-G1", replacement)
            self.assertInvalid(validate_chapter_table(text, self.root))

    def test_supersedes_requires_preserved_history(self):
        self.rows[0]["supersedes"] = "missing-old-chapter"
        self.assertInvalid(self.check())
        self.rows[0]["supersedes"] = "split:old-chapter"
        self.assertInvalid(self.check())
        self.rows.append(dict(self.rows[0], 章ID="old-chapter", 状態="tombstone", supersedes="-"))
        self.assertInvalid(self.check())  # split先が1つだけ
        self.rows[1]["supersedes"] = "split:old-chapter"
        self.assertTrue(self.check()["draftStructureValid"], self.check())
        self.rows[1]["supersedes"] = "merge:old-chapter,missing-chapter"
        self.assertInvalid(self.check())

    def test_merge_and_unstarted_rename_preserve_ids(self):
        self.rows.extend(dict(self.rows[0], 章ID=name, 状態="tombstone", supersedes="-")
                         for name in ("old-first", "old-second"))
        self.rows[0]["supersedes"] = "merge:old-first,old-second"
        self.assertTrue(self.check()["draftStructureValid"], self.check())
        self.rows[1]["supersedes"] = "rename:old-name"
        self.assertTrue(self.check()["draftStructureValid"], self.check())
        self.rows[1]["状態"] = "実装済"  # 操作時の未着手条件と、後の履歴維持は別
        self.assertTrue(self.check()["draftStructureValid"], self.check())
        self.rows[2]["supersedes"] = "rename:old-name"
        self.assertInvalid(self.check())
        self.rows[2]["supersedes"] = "-"
        self.rows.append(dict(self.rows[0], 章ID="old-name", 状態="tombstone", supersedes="-"))
        self.assertInvalid(self.check())

    def test_retired_successor_keeps_its_history_without_cycles(self):
        self.rows.extend([
            dict(self.rows[0], 章ID="old-first", 状態="tombstone", supersedes="-"),
            dict(self.rows[0], 章ID="old-second", 状態="tombstone", supersedes="rename:old-name"),
        ])
        self.rows[0]["supersedes"] = "merge:old-first,old-second"
        self.assertTrue(self.check()["draftStructureValid"], self.check())
        self.rows[-2]["supersedes"] = "merge:old-second,old-first"
        self.assertInvalid(self.check())

    def test_supersedes_cycle_is_rejected_independently_of_current_dependencies(self):
        self.rows.extend([
            dict(self.rows[0], 章ID="old-first", 状態="tombstone", supersedes="split:old-second"),
            dict(self.rows[0], 章ID="old-second", 状態="tombstone", supersedes="split:old-first"),
        ])
        self.rows[0]["supersedes"] = "split:old-first"
        self.rows[1]["supersedes"] = "split:old-second"
        result = self.check()
        self.assertInvalid(result)
        self.assertIn("履歴が循環", result["errors"][0])

    def test_invalid_id_order_part_status_or_required_value(self):
        original = copy.deepcopy(self.rows)
        for column, value in (("章ID", "Bad-id"), ("章ID", "a"), ("章ID", "a" * 33),
                              ("章ID", "chapter-01"), ("並び順", "zero"),
                              ("パート", "F"), ("状態", "DRAFT"), ("地図", ""),
                              ("最初の結果", "-"), ("見える変化", "none"),
                              ("未決依存", "not-a-backlog-id"), ("節目", "maybe")):
            self.rows = copy.deepcopy(original)
            self.rows[0][column] = value
            with self.subTest(column=column, value=value):
                self.assertInvalid(self.check())

    def test_duplicate_ids_orders_and_reused_tombstone_fail(self):
        self.rows.append(dict(self.rows[0], 状態="tombstone"))
        self.assertInvalid(self.check())
        self.rows.pop()
        self.rows[1]["並び順"] = self.rows[0]["並び順"]
        result = self.check()
        self.assertInvalid(result)
        self.assertIn("並び順が重複", result["errors"][0])

    def test_order_is_an_integer_not_an_implicit_positive_chapter_number(self):
        self.rows[0]["並び順"] = "-10"
        self.assertTrue(self.check()["draftStructureValid"], self.check())

    def test_missing_future_and_cyclic_prerequisites_fail(self):
        for dependency in ("missing-chapter", self.rows[-1]["章ID"], self.rows[0]["章ID"]):
            with self.subTest(dependency=dependency):
                self.rows[0]["前提とする前章成果"] = dependency
                self.assertInvalid(self.check())

    def test_missing_part_and_fr_fail(self):
        self.rows[-1]["パート"] = "D"
        self.assertInvalid(self.check())
        self.rows[-1]["パート"] = "E"
        self.traces[2]["FR"] = "FR1"
        self.assertInvalid(self.check())

    def test_all_parts_and_numeric_order_are_checked(self):
        for row in self.rows[-3:]:
            row["見える変化"] = "tool"
        self.rows.reverse()
        self.assertInvalid(self.check())

    def test_tombstones_are_history_not_current_coverage(self):
        self.rows.append(dict(self.rows[0], 章ID="old-chapter", 状態="tombstone"))
        self.assertTrue(self.check()["draftStructureValid"])
        self.rows[1]["前提とする前章成果"] = "old-chapter"
        self.assertInvalid(self.check())
        self.rows[1]["前提とする前章成果"] = self.rows[0]["章ID"]
        self.traces.append(dict(self.traces[0], 章ID="old-chapter", FR="FR1"))
        self.assertInvalid(self.check())

    def test_invalid_trace_or_missing_current_reference_fails(self):
        original = copy.deepcopy(self.traces)
        for column, value in (("章ID", "missing-chapter"), ("FR", "FR16"),
                              ("テスト", ""), ("証拠", "missing.md"),
                              ("証拠", "../outside.md")):
            self.traces = copy.deepcopy(original)
            self.traces[0][column] = value
            with self.subTest(column=column):
                self.assertInvalid(self.check())
        self.traces = original[:-1]
        self.assertInvalid(self.check())

    def exception(self):
        ids = ",".join(r["章ID"] for r in self.rows[-3:])
        for row in self.rows[-3:]:
            row["見える変化"] = "tool"
        common = f"版: test-v1\n対象章: {ids}\nゲート: G1\n種別: tool連続例外\n範囲: sns-app/material/18_章分割表.md\n"
        (self.root / "adr.md").write_text(common + "理由: 開発順序を守る\n", encoding="utf-8")
        (self.root / "approval.md").write_text(common + "判断: 承認\n承認者: 局長\nADR: adr.md\n", encoding="utf-8")
        return "\n## tool連続例外\n" + table(("対象章", "ADR", "承認記録"), [
            {"対象章": ids, "ADR": "adr.md", "承認記録": "approval.md"}])

    def test_exception_requires_matching_records(self):
        extra = self.exception()
        self.assertTrue(self.check(extra)["draftStructureValid"], self.check(extra))
        path = self.root / "approval.md"
        original = path.read_text(encoding="utf-8")
        for old, new in (("test-v1", "old-v0"), ("ゲート: G1", "ゲート: G3"),
                         ("判断: 承認", "判断: 未承認"), ("承認者: 局長", "承認者: 作者"),
                         ("ADR: adr.md", "ADR: fake.md"), ("chapter-dx", "missing-chapter"),
                         ("範囲: sns-app/material/18_章分割表.md", "範囲: 別教材")):
            path.write_text(original.replace(old, new), encoding="utf-8")
            with self.subTest(old=old):
                self.assertInvalid(self.check(extra))
        path.unlink()
        self.assertInvalid(self.check(extra))

    def test_fake_adr_and_inline_approval_do_not_exempt(self):
        extra = self.exception()
        (self.root / "adr.md").unlink()
        self.assertInvalid(self.check(extra))
        self.assertInvalid(self.check("\n承認: true\n"))

    def test_cli_empty_and_missing_input_are_nonzero(self):
        path = self.root / "empty.md"
        path.write_text("", encoding="utf-8")
        for candidate in (path, self.root / "missing.md"):
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("chapter_table.py")),
                                     str(candidate)], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)["draftStructureValid"])


if __name__ == "__main__":
    unittest.main()
