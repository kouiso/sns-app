from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from g6_support import (
    G6ResultError,
    dev_log_evidence,
    exec_pass,
    parse_result,
    read_choice,
)


TOOLS_DIR = Path(__file__).resolve().parent


def obj(mode: str = "exec", **overrides: object) -> str:
    value: dict[str, object] = {
        "adapter": "test",
        "r1_reached": True,
        "r2_stuck": [],
        "r3_external_knowledge": [],
        "r4_unavailable": [],
    }
    if mode == "read":
        value = {
            "adapter": "test",
            "choice": "A",
            "reason": "clear",
            "boring_a": [],
            "boring_b": [],
        }
    value.update(overrides)
    return json.dumps(value)


class SupportTests(unittest.TestCase):
    def test_exec_requires_independent_validator_and_all_clean_receipt_fields(self) -> None:
        result = parse_result(obj(), "exec")
        self.assertTrue(exec_pass(result, True))
        self.assertFalse(exec_pass(result, False))
        self.assertFalse(
            exec_pass(parse_result(obj(r2_stuck=["blocked"]), "exec"), True)
        )
        self.assertFalse(
            exec_pass(
                parse_result(obj(r3_external_knowledge=["unstated setup"]), "exec"),
                True,
            )
        )
        self.assertFalse(
            exec_pass(parse_result(obj(r4_unavailable=["QR"]), "exec"), True)
        )

    def test_exec_rejects_self_declared_or_non_json_result(self) -> None:
        with self.assertRaises(G6ResultError):
            parse_result(obj(objective_validated=True), "exec")
        with self.assertRaises(G6ResultError):
            parse_result("R1-到達: できた", "exec")

    def test_result_schema_is_closed_and_read_choice_is_strict(self) -> None:
        with self.assertRaises(G6ResultError):
            parse_result(obj(extra="ignored"), "exec")
        result = parse_result(obj("read"), "read")
        self.assertEqual(read_choice(result), "A")
        with self.assertRaises(G6ResultError):
            read_choice({"choice": "maybe"})

    def test_json_rejects_duplicates_nan_and_wrong_types(self) -> None:
        duplicate = (
            '{"adapter":"x","choice":"A","choice":"B","reason":"r",'
            '"boring_a":[],"boring_b":[]}'
        )
        with self.assertRaises(G6ResultError):
            parse_result(duplicate, "read")
        with self.assertRaises(G6ResultError):
            parse_result(obj("read").replace('"choice": "A"', '"choice": NaN'), "read")
        with self.assertRaises(G6ResultError):
            parse_result(obj("read", boring_a="none"), "read")
        with self.assertRaises(G6ResultError):
            parse_result(obj("read", reason=False), "read")

    def test_dev_log_evidence_counts_only_canonical_high_value_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.md"
            raw = (
                "# log\n"
                "G6_HIGH_VALUE_CLASSIFICATION: complete\n"
                "- G6_HIGH_VALUE: 高\n"
                "- **G6_HIGH_VALUE**: **高**\n"
                "  - G6_HIGH_VALUE: 低 — 観測根拠に基づく分類。\n"
            ).encode()
            path.write_bytes(raw)
            count, classified, digest = dev_log_evidence(path)
        self.assertEqual(2, count)
        self.assertEqual(3, classified)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)

    def test_dev_log_record_without_complete_classification_is_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.md"
            path.write_text("# log\nrecord only\n", encoding="utf-8")
            with self.assertRaises(G6ResultError):
                dev_log_evidence(path)

    def test_dev_log_rejects_malformed_or_unclassified_value_lines(self) -> None:
        samples = (
            "G6_HIGH_VALUE_CLASSIFICATION: complete\n- G6_HIGH_VALUE: maybe\n",
            "G6_HIGH_VALUE_CLASSIFICATION: complete\n"
            "G6_HIGH_VALUE_ITEMS: 0\n- 教材に載せる価値: 高\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.md"
            for sample in samples:
                path.write_text(sample, encoding="utf-8")
                with self.assertRaises(G6ResultError):
                    dev_log_evidence(path)


FAKE_DROID = r"""#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
required = [
    "exec",
    "--model",
    "gemini-3.8-flash",
    "--reasoning-effort",
    "medium",
    "--only-tools",
    "Read",
    "--disable-builtin-skills",
    "-f",
]
if args[:len(required)] != required or len(args) != len(required) + 1:
    raise SystemExit(64)

round_name = os.environ["G6_ROUND"]
attempt = int(os.environ["G6_ATTEMPT"])
participant = int(os.environ["G6_PARTICIPANT"])
scenario = os.environ["FAKE_DROID_SCENARIO"]
a = Path("A.md").read_bytes()
b = Path("B.md").read_bytes()
real = "A" if b"REAL_BODY" in a else "B"
other = "B" if real == "A" else "A"

record = {
    "round": round_name,
    "attempt": attempt,
    "participant": participant,
    "real": real,
    "a_sha256": hashlib.sha256(a).hexdigest(),
    "b_sha256": hashlib.sha256(b).hexdigest(),
    "args": args,
    "room_files": sorted(path.name for path in Path(".").iterdir()),
}
fd = os.open(os.environ["FAKE_DROID_LOG"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
try:
    os.write(fd, (json.dumps(record, sort_keys=True) + "\n").encode())
finally:
    os.close(fd)

if scenario == "nonzero" and round_name == "plain" and participant == 2:
    raise SystemExit(9)
if scenario == "bad-json" and round_name == "plain" and participant == 4:
    print('{"adapter":')
    raise SystemExit(0)

choice = real
if scenario == "retry" and attempt == 1 and participant == 4:
    choice = other
print(json.dumps({
    "adapter": "fake-droid",
    "choice": choice,
    "reason": "fixture choice",
    "boring_a": [],
    "boring_b": [],
}))
"""


class RunnerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "prototype"
        self.tools = self.root / "tools"
        self.controls = self.root / "g6" / "sample"
        self.dev_logs = self.base / "dev-logs"
        self.work = self.base / "work"
        self.tools.mkdir(parents=True)
        self.controls.mkdir(parents=True)
        self.dev_logs.mkdir()
        self.work.mkdir()

        for name in ("g6-run.sh", "g6_support.py"):
            shutil.copy2(TOOLS_DIR / name, self.tools / name)
        (self.tools / "g6-run.sh").chmod(0o755)
        (self.root / "chapter-sample.md").write_text(
            "# Real\n\nREAL_BODY\n", encoding="utf-8"
        )
        (self.controls / "plain.md").write_text(
            "<!-- 抜いた要素: 対話 -->\nPLAIN_BODY\n", encoding="utf-8"
        )
        (self.controls / "minus.md").write_text(
            "<!-- 抜いた要素: 高価値の詰まり -->\nMINUS_BODY\n",
            encoding="utf-8",
        )
        self.dev_log = self.dev_logs / "sample.md"
        self.dev_log.write_text(
            "# log\nG6_HIGH_VALUE_CLASSIFICATION: complete\n"
            "- G6_HIGH_VALUE: 高\n",
            encoding="utf-8",
        )
        self.fake = self.base / "fake-droid"
        self.fake.write_text(FAKE_DROID, encoding="utf-8")
        self.fake.chmod(0o755)
        self.fake_log = self.base / "fake.log"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_g6(
        self, scenario: str, mode: str = "read", **extra_env: str
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "DROID_BIN": str(self.fake),
                "FAKE_DROID_LOG": str(self.fake_log),
                "FAKE_DROID_SCENARIO": scenario,
                "G6_READERS": "4",
                "G6_TIMEOUT_SECONDS": "10",
                "TMPDIR": str(self.work),
            }
        )
        env.update(extra_env)
        return subprocess.run(
            [str(self.tools / "g6-run.sh"), "sample", mode],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def records(self) -> list[dict[str, object]]:
        if not self.fake_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.fake_log.read_text(encoding="utf-8").splitlines()
        ]

    def test_counterbalances_and_completes_both_required_rounds(self) -> None:
        result = self.run_g6("all-real")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("PROVISIONAL_PASS / NON-FORMAL G6", result.stdout)
        records = self.records()
        self.assertEqual(8, len(records))
        self.assertEqual({"plain", "minus"}, {record["round"] for record in records})
        for round_name in ("plain", "minus"):
            positions = [
                record["real"]
                for record in records
                if record["round"] == round_name
            ]
            self.assertEqual(2, positions.count("A"))
            self.assertEqual(2, positions.count("B"))
        for record in records:
            args = record["args"]
            self.assertIn("--only-tools", args)
            self.assertEqual("Read", args[args.index("--only-tools") + 1])
            self.assertEqual(["A.md", "B.md"], record["room_files"])

    def test_three_votes_cannot_hide_fourth_participant_bad_json(self) -> None:
        result = self.run_g6("bad-json")
        self.assertEqual(2, result.returncode)
        self.assertIn("invalid JSON", result.stderr)
        self.assertNotIn("PROVISIONAL_PASS", result.stdout)

    def test_nonzero_adapter_exit_fails_closed(self) -> None:
        result = self.run_g6("nonzero")
        self.assertEqual(2, result.returncode)
        self.assertIn("exited 9", result.stderr)

    def test_exact_threshold_retries_same_comparison_for_each_round(self) -> None:
        result = self.run_g6("retry")
        self.assertEqual(0, result.returncode, result.stderr)
        records = self.records()
        self.assertEqual(16, len(records))
        self.assertEqual(
            {("plain", 1), ("plain", 2), ("minus", 1), ("minus", 2)},
            {(record["round"], record["attempt"]) for record in records},
        )
        for round_name in ("plain", "minus"):
            for participant in range(1, 5):
                pair = [
                    record
                    for record in records
                    if record["round"] == round_name
                    and record["participant"] == participant
                ]
                self.assertEqual(2, len(pair))
                self.assertEqual(pair[0]["a_sha256"], pair[1]["a_sha256"])
                self.assertEqual(pair[0]["b_sha256"], pair[1]["b_sha256"])

    def test_zero_high_value_entries_records_r2_na_without_minus(self) -> None:
        self.dev_log.write_text(
            "# log\nG6_HIGH_VALUE_CLASSIFICATION: complete\n"
            "  - G6_HIGH_VALUE: 対象外 — 環境固有。\n"
            "  - G6_HIGH_VALUE: 低 — 教材上の詰まりではない。\n",
            encoding="utf-8",
        )
        expected_hash = hashlib.sha256(self.dev_log.read_bytes()).hexdigest()
        (self.controls / "minus.md").unlink()
        result = self.run_g6("all-real", G6_HIGH_VALUE_COUNT="99")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(
            f"R2=N/A HIGH_VALUE_COUNT=0 CLASSIFIED_ITEM_COUNT=2 DEV_LOG_SHA256={expected_hash}",
            result.stdout,
        )
        self.assertEqual({"plain"}, {record["round"] for record in self.records()})

    def test_env_zero_cannot_override_high_value_dev_log_or_missing_minus(self) -> None:
        (self.controls / "minus.md").unlink()
        result = self.run_g6("all-real", G6_HIGH_VALUE_COUNT="0")
        self.assertEqual(1, result.returncode)
        self.assertIn("高価値の詰まりが 1 件", result.stderr)
        self.assertEqual([], self.records())

    def test_record_only_log_cannot_claim_r2_na(self) -> None:
        self.dev_log.write_text("# log\nrecord only\n", encoding="utf-8")
        (self.controls / "minus.md").unlink()
        result = self.run_g6("all-real", G6_HIGH_VALUE_COUNT="0")
        self.assertEqual(1, result.returncode)
        self.assertIn("G6_HIGH_VALUE_CLASSIFICATION", result.stderr)
        self.assertEqual([], self.records())

    def test_exec_stops_before_launching_adapter(self) -> None:
        result = self.run_g6("all-real", mode="exec")
        self.assertEqual(2, result.returncode)
        self.assertIn("NOT_READY", result.stderr)
        self.assertEqual([], self.records())


if __name__ == "__main__":
    unittest.main(verbosity=2)
