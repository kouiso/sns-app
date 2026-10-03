from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from d4_run_clock import DB_NAME, D4RunClock, RunBinding, RunClockError


BOOT_A = "11111111-1111-4111-8111-111111111111"
BOOT_B = "22222222-2222-4222-8222-222222222222"


class FakeClock:
    def __init__(self, *, mono: int = 1_000, boot: str = BOOT_A) -> None:
        self._lock = threading.Lock()
        self.mono = mono
        self.utc = datetime(2026, 10, 3, tzinfo=timezone.utc)
        self.boot = boot

    def utc_now(self) -> datetime:
        with self._lock:
            return self.utc

    def monotonic_ns(self) -> int:
        with self._lock:
            return self.mono

    def boot_id(self) -> str:
        with self._lock:
            return self.boot

    def advance(self, nanoseconds: int) -> None:
        with self._lock:
            self.mono += nanoseconds
            self.utc += timedelta(microseconds=nanoseconds / 1_000)


def binding(run_id: str = "1" * 32, *, chapter: str = "a" * 64) -> RunBinding:
    return RunBinding(
        run_id=run_id,
        chapter_sha256=chapter,
        start_sha256="b" * 64,
        manifest_sha256="c" * 64,
        objective_sha256="d" * 64,
        profile="heavy-v1",
    )


class RunClockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "clock"
        self.clock = FakeClock()
        self.binding = binding()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def start(self) -> D4RunClock:
        return D4RunClock.start(self.root, self.binding, _clock=self.clock)

    def test_overlap_totals_are_labeled_and_not_run_or_active_time(self):
        ledger = self.start()
        first = ledger.begin_span(
            actor="gemini",
            phase="model",
            operation="draft",
            input_hashes={"App.tsx": "1" * 64},
        )
        self.clock.advance(10_000)
        second = ledger.begin_span(
            actor="controller",
            phase="control_wait",
            operation="wait-ui",
            input_hashes={},
        )
        self.clock.advance(20_000)
        ledger.finish_span(span_id=first, outcome="succeeded", output_hashes={"draft": "2" * 64})
        self.clock.advance(10_000)
        ledger.finish_span(span_id=second, outcome="failed", output_hashes={"log": "3" * 64})

        summary = ledger.summarize()
        self.assertEqual(summary["run_elapsed_ns"], 40_000)
        self.assertEqual([span["elapsed_ns"] for span in summary["spans"]], [30_000, 30_000])
        self.assertGreater(
            sum(summary["per_actor_span_wall_ns_possibly_overlapping"].values()),
            summary["run_elapsed_ns"],
        )
        self.assertTrue(summary["span_wall_totals_may_overlap"])
        self.assertTrue(summary["span_wall_totals_are_not_run_elapsed"])
        self.assertTrue(summary["model_wall_is_not_active_or_token_time"])
        self.assertIsNone(summary["human_active_ns"])
        self.assertFalse(summary["active_time_measured"])

    def test_duplicate_start_and_binding_mismatch_are_rejected(self):
        self.start()
        with self.assertRaisesRegex(RunClockError, "run already exists"):
            D4RunClock.start(self.root, self.binding, _clock=self.clock)
        with self.assertRaisesRegex(RunClockError, "run binding mismatch"):
            D4RunClock.resume(self.root, binding(chapter="e" * 64), _clock=self.clock)

    def test_crash_reopen_preserves_open_span_and_allows_explicit_finish(self):
        ledger = self.start()
        span_id = ledger.begin_span(
            actor="opus",
            phase="implementation",
            operation="edit-source",
            input_hashes={"source": "4" * 64},
        )
        del ledger
        self.clock.advance(5_000)

        resumed = D4RunClock.resume(self.root, self.binding, _clock=self.clock)
        open_summary = resumed.summarize()
        self.assertEqual(open_summary["unfinished_span_ids"], [span_id])
        self.assertEqual(open_summary["spans"][0]["outcome"], "OPEN")
        self.assertIsNone(open_summary["spans"][0]["ended_at_utc"])

        resumed.finish_span(span_id=span_id, outcome="failed", output_hashes={})
        self.assertEqual(resumed.summarize()["unfinished_span_ids"], [])

    def test_binding_tamper_is_detected_on_every_operation(self):
        ledger = self.start()
        with sqlite3.connect(self.root / DB_NAME) as connection:
            connection.execute("UPDATE runs SET objective_sha256 = ?", ("e" * 64,))
        with self.assertRaisesRegex(RunClockError, "run binding mismatch"):
            ledger.summarize()

    def test_retry_requires_an_ended_failed_parent(self):
        ledger = self.start()
        with self.assertRaisesRegex(RunClockError, "retry parent does not exist"):
            ledger.begin_span(
                actor="gemini", phase="model", operation="future-retry",
                input_hashes={}, retry_of="9" * 32,
            )
        open_parent = ledger.begin_span(
            actor="gemini", phase="model", operation="open-parent", input_hashes={},
        )
        with self.assertRaisesRegex(RunClockError, "ended failed span"):
            ledger.begin_span(
                actor="gemini", phase="model", operation="early-retry",
                input_hashes={}, retry_of=open_parent,
            )
        ledger.finish_span(span_id=open_parent, outcome="succeeded", output_hashes={})
        with self.assertRaisesRegex(RunClockError, "ended failed span"):
            ledger.begin_span(
                actor="gemini", phase="model", operation="success-retry",
                input_hashes={}, retry_of=open_parent,
            )
        failed_parent = ledger.begin_span(
            actor="gemini", phase="model", operation="failed-parent", input_hashes={},
        )
        ledger.finish_span(span_id=failed_parent, outcome="failed", output_hashes={})
        retry = ledger.begin_span(
            actor="gemini", phase="model", operation="valid-retry",
            input_hashes={}, retry_of=failed_parent,
        )
        self.assertEqual(ledger.summarize()["retries"], [{"span_id": retry, "retry_of": failed_parent}])

    def test_clock_reverse_and_boot_change_are_rejected(self):
        self.start()
        self.clock.advance(10_000)
        current_utc = self.clock.utc
        D4RunClock.resume(self.root, self.binding, _clock=self.clock)
        self.clock.mono = 500
        with self.assertRaisesRegex(RunClockError, "clock moved backwards"):
            D4RunClock.resume(self.root, self.binding, _clock=self.clock)
        self.clock.mono = 11_000
        self.clock.utc = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with self.assertRaisesRegex(RunClockError, "clock moved backwards"):
            D4RunClock.resume(self.root, self.binding, _clock=self.clock)
        self.clock.utc = current_utc
        self.clock.boot = BOOT_B
        with self.assertRaisesRegex(RunClockError, "boot ID changed"):
            D4RunClock.resume(self.root, self.binding, _clock=self.clock)

    def test_resume_persists_latest_sample_for_future_reverse_check(self):
        self.start()
        self.clock.advance(10_000)
        D4RunClock.resume(self.root, self.binding, _clock=self.clock)
        self.clock.mono = 5_000
        with self.assertRaisesRegex(RunClockError, "clock moved backwards"):
            D4RunClock.resume(self.root, self.binding, _clock=self.clock)

    def test_summary_persists_latest_sample_and_rejected_operation_rolls_back(self):
        ledger = self.start()
        self.clock.advance(10_000)
        ledger.summarize()
        self.clock.mono = 5_000
        with self.assertRaisesRegex(RunClockError, "clock moved backwards"):
            ledger.summarize()

        rollback_root = self.base / "rollback-clock"
        rollback_clock = FakeClock()
        rollback_binding = binding("8" * 32)
        rollback_ledger = D4RunClock.start(rollback_root, rollback_binding, _clock=rollback_clock)
        rollback_clock.advance(10_000)
        with self.assertRaisesRegex(RunClockError, "retry parent does not exist"):
            rollback_ledger.begin_span(
                actor="gemini", phase="model", operation="rejected-retry",
                input_hashes={}, retry_of="9" * 32,
            )
        rollback_clock.mono = 5_000
        summary = rollback_ledger.summarize()
        self.assertEqual(summary["run_elapsed_ns"], 4_000)

    def test_resume_migrates_prior_schema_and_initializes_latest_sample(self):
        self.root.mkdir(mode=0o700)
        db_path = self.root / DB_NAME
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """CREATE TABLE runs (
                    run_id TEXT PRIMARY KEY,
                    chapter_sha256 TEXT NOT NULL,
                    start_sha256 TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    objective_sha256 TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    boot_id TEXT NOT NULL,
                    started_utc TEXT NOT NULL,
                    started_mono INTEGER NOT NULL
                )"""
            )
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.binding.run_id,
                    self.binding.chapter_sha256,
                    self.binding.start_sha256,
                    self.binding.manifest_sha256,
                    self.binding.objective_sha256,
                    self.binding.profile,
                    BOOT_A,
                    "2026-10-03T00:00:00.000000Z",
                    1_000,
                ),
            )
        os.chmod(db_path, 0o600)

        self.clock.advance(5_000)
        D4RunClock.resume(self.root, self.binding, _clock=self.clock)
        with sqlite3.connect(db_path) as connection:
            row = connection.execute(
                "SELECT last_sample_utc, last_sample_mono FROM runs WHERE run_id = ?",
                (self.binding.run_id,),
            ).fetchone()
        self.assertEqual(row, ("2026-10-03T00:00:00.000005Z", 6_000))

    def test_concurrent_writers_append_distinct_open_spans(self):
        D4RunClock.start(self.root, self.binding)

        def append(index: int) -> str:
            ledger = D4RunClock.resume(self.root, self.binding)
            return ledger.begin_span(
                actor=f"actor-{index}",
                phase="implementation",
                operation="parallel-edit",
                input_hashes={"input": f"{index + 1:064x}"},
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            span_ids = list(pool.map(append, range(12)))
        summary = D4RunClock.resume(self.root, self.binding).summarize()
        self.assertEqual(len(set(span_ids)), 12)
        self.assertEqual(set(summary["unfinished_span_ids"]), set(span_ids))

    def test_source_contents_are_rejected_and_only_hashes_are_reported(self):
        ledger = self.start()
        secret_source = "const privatePassword = 'do-not-copy';"
        with self.assertRaisesRegex(RunClockError, "invalid input hashes"):
            ledger.begin_span(
                actor="gemini",
                phase="model",
                operation="hash-only",
                input_hashes={"App.tsx": secret_source},
            )
        digest = "5" * 64
        ledger.begin_span(
            actor="gemini", phase="model", operation="hash-only",
            input_hashes={"App.tsx": digest},
        )
        serialized = str(ledger.summarize())
        self.assertIn(digest, serialized)
        self.assertNotIn(secret_source, serialized)
        self.assertNotIn(secret_source.encode(), (self.root / DB_NAME).read_bytes())

    def test_invalid_and_oversized_arguments_are_rejected(self):
        ledger = self.start()
        invalid_calls = [
            {"actor": True, "phase": "model", "operation": "work", "input_hashes": {}},
            {"actor": "gemini", "phase": "unknown", "operation": "work", "input_hashes": {}},
            {"actor": "gemini", "phase": "model", "operation": "x" * 65, "input_hashes": {}},
            {"actor": "gemini", "phase": "model", "operation": "work", "input_hashes": {"../source": "1" * 64}},
            {"actor": "gemini", "phase": "model", "operation": "work", "input_hashes": {str(i): "1" * 64 for i in range(65)}},
        ]
        for arguments in invalid_calls:
            with self.subTest(arguments=arguments), self.assertRaises(RunClockError):
                ledger.begin_span(**arguments)
        with self.assertRaises(TypeError):
            ledger.begin_span(
                actor="gemini", phase="model", operation="work", input_hashes={}, unknown=True,
            )
        with self.assertRaises(RunClockError):
            RunBinding(True, "a" * 64, "b" * 64, "c" * 64, "d" * 64, "heavy-v1")

    def test_bad_modes_symlinks_and_nonregular_nodes_are_rejected(self):
        self.start()
        self.assertEqual(os.stat(self.root).st_mode & 0o7777, 0o700)
        self.assertEqual(os.stat(self.root / DB_NAME).st_mode & 0o7777, 0o600)

        bad_mode = self.base / "bad-mode"
        bad_mode.mkdir(mode=0o755)
        os.chmod(bad_mode, 0o755)
        with self.assertRaisesRegex(RunClockError, "directory mode"):
            D4RunClock.start(bad_mode, binding("2" * 32), _clock=self.clock)

        real = self.base / "real"
        real.mkdir(mode=0o700)
        linked = self.base / "linked"
        linked.symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(RunClockError, "ledger directory"):
            D4RunClock.start(linked, binding("3" * 32), _clock=self.clock)

        db_link_root = self.base / "db-link-root"
        db_link_root.mkdir(mode=0o700)
        target = self.base / "target.sqlite"
        target.write_bytes(b"")
        os.chmod(target, 0o600)
        (db_link_root / DB_NAME).symlink_to(target)
        with self.assertRaisesRegex(RunClockError, "run ledger"):
            D4RunClock.start(db_link_root, binding("4" * 32), _clock=self.clock)

        db_mode_root = self.base / "db-mode-root"
        db_mode_root.mkdir(mode=0o700)
        db_file = db_mode_root / DB_NAME
        db_file.write_bytes(b"")
        os.chmod(db_file, 0o644)
        with self.assertRaisesRegex(RunClockError, "ledger mode"):
            D4RunClock.start(db_mode_root, binding("5" * 32), _clock=self.clock)

        db_directory_root = self.base / "db-directory-root"
        db_directory_root.mkdir(mode=0o700)
        (db_directory_root / DB_NAME).mkdir(mode=0o700)
        with self.assertRaisesRegex(RunClockError, "run ledger"):
            D4RunClock.start(db_directory_root, binding("6" * 32), _clock=self.clock)

    def test_duplicate_finish_and_formal_completion_are_impossible(self):
        ledger = self.start()
        span_id = ledger.begin_span(
            actor="controller", phase="g6_read", operation="read-only", input_hashes={},
        )
        ledger.finish_span(span_id=span_id, outcome="succeeded", output_hashes={})
        with self.assertRaisesRegex(RunClockError, "already finished"):
            ledger.finish_span(span_id=span_id, outcome="failed", output_hashes={})
        with self.assertRaisesRegex(RunClockError, "invalid span outcome"):
            ledger.finish_span(span_id="7" * 32, outcome="complete", output_hashes={})
        summary = ledger.summarize()
        self.assertEqual(summary["status"], "OPEN")
        self.assertFalse(summary["formal_g6_pass"])
        self.assertFalse(summary["formal_d4_complete"])
        self.assertFalse(hasattr(ledger, "close"))
        self.assertFalse(hasattr(ledger, "complete"))
        self.assertFalse(hasattr(ledger, "mark_formal_pass"))


if __name__ == "__main__":
    unittest.main()
