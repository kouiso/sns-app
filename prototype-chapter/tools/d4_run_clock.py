"""Durable, non-formal wall-clock evidence for a future trusted D4 controller.

The production API samples its own UTC, monotonic clock, and Linux boot ID.
``_clock`` injection exists only for deterministic trusted local tests. This
module cannot close a run, infer human-active time, or assert D4/G6 completion.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import stat
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


DB_NAME = "d4-run-clock.sqlite3"
RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
HASH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
BOOT_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
PHASES = frozenset({
    "implementation",
    "model",
    "control_wait",
    "screenshot",
    "plain_create",
    "minus_create",
    "plain_update",
    "minus_update",
    "g6_read",
    "g6_exec",
})
OUTCOMES = frozenset({"succeeded", "failed"})
MAX_HASHES = 64
MAX_HASHES_JSON_BYTES = 16 * 1024


class RunClockError(ValueError):
    """A fixed public error type for invalid state, input, or storage."""


@dataclass(frozen=True)
class RunBinding:
    run_id: str
    chapter_sha256: str
    start_sha256: str
    manifest_sha256: str
    objective_sha256: str
    profile: str

    def __post_init__(self) -> None:
        if type(self.run_id) is not str or not RUN_ID_RE.fullmatch(self.run_id):
            raise RunClockError("invalid run binding")
        for value in (
            self.chapter_sha256,
            self.start_sha256,
            self.manifest_sha256,
            self.objective_sha256,
        ):
            if type(value) is not str or not SHA256_RE.fullmatch(value):
                raise RunClockError("invalid run binding")
        if type(self.profile) is not str or not SAFE_ID_RE.fullmatch(self.profile):
            raise RunClockError("invalid run binding")


class _Clock(Protocol):
    def utc_now(self) -> datetime: ...
    def monotonic_ns(self) -> int: ...
    def boot_id(self) -> str: ...


class _SystemClock:
    def utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def boot_id(self) -> str:
        try:
            value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip().lower()
        except (OSError, UnicodeError) as exc:
            raise RunClockError("Linux boot ID unavailable") from exc
        if not BOOT_ID_RE.fullmatch(value):
            raise RunClockError("invalid Linux boot ID")
        return value


@dataclass(frozen=True)
class _Sample:
    utc: str
    monotonic_ns: int
    boot_id: str


def _utc_text(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise RunClockError("invalid clock sample")
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_safe_id(value: object, label: str) -> str:
    if type(value) is not str or not SAFE_ID_RE.fullmatch(value):
        raise RunClockError(f"invalid {label}")
    return value


def _validate_span_id(value: object, label: str = "span ID") -> str:
    if type(value) is not str or not RUN_ID_RE.fullmatch(value):
        raise RunClockError(f"invalid {label}")
    return value


def _validate_hashes(value: object, label: str) -> tuple[dict[str, str], str]:
    if type(value) is not dict or len(value) > MAX_HASHES:
        raise RunClockError(f"invalid {label}")
    normalized: dict[str, str] = {}
    for name, digest in value.items():
        if type(name) is not str or not HASH_NAME_RE.fullmatch(name):
            raise RunClockError(f"invalid {label}")
        if name.startswith("/") or "//" in name or ".." in name.split("/"):
            raise RunClockError(f"invalid {label}")
        if type(digest) is not str or not SHA256_RE.fullmatch(digest):
            raise RunClockError(f"invalid {label}")
        normalized[name] = digest
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_HASHES_JSON_BYTES:
        raise RunClockError(f"invalid {label}")
    return normalized, encoded


class D4RunClock:
    """Append-only span timing for one open run.

    Use :meth:`start` once, then :meth:`resume` after process restarts. Every
    method reopens and locks the ledger, so a crashed process leaves any begun
    span visibly OPEN. There is intentionally no close or formal-pass method.
    """

    def __init__(self, directory: Path, binding: RunBinding, clock: _Clock) -> None:
        self._directory = directory
        self._db_path = directory / DB_NAME
        self._binding = binding
        self._clock = clock

    @classmethod
    def start(
        cls,
        directory: Path,
        binding: RunBinding,
        *,
        _clock: _Clock | None = None,
    ) -> "D4RunClock":
        instance = cls._prepare(directory, binding, _clock)
        with instance._transaction() as connection:
            instance._create_schema(connection)
            if connection.execute("SELECT 1 FROM runs WHERE run_id = ?", (binding.run_id,)).fetchone():
                raise RunClockError("run already exists")
            sample = instance._raw_sample()
            connection.execute(
                """INSERT INTO runs (
                    run_id, chapter_sha256, start_sha256, manifest_sha256,
                    objective_sha256, profile, boot_id, started_utc, started_mono,
                    last_sample_utc, last_sample_mono
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    binding.run_id,
                    binding.chapter_sha256,
                    binding.start_sha256,
                    binding.manifest_sha256,
                    binding.objective_sha256,
                    binding.profile,
                    sample.boot_id,
                    sample.utc,
                    sample.monotonic_ns,
                    sample.utc,
                    sample.monotonic_ns,
                ),
            )
        return instance

    @classmethod
    def resume(
        cls,
        directory: Path,
        binding: RunBinding,
        *,
        _clock: _Clock | None = None,
    ) -> "D4RunClock":
        instance = cls._prepare(directory, binding, _clock, require_database=True)
        with instance._transaction() as connection:
            instance._create_schema(connection)
            instance._verified_sample(connection)
        return instance

    @classmethod
    def _prepare(
        cls,
        directory: Path,
        binding: RunBinding,
        clock: _Clock | None,
        *,
        require_database: bool = False,
    ) -> "D4RunClock":
        if not isinstance(directory, Path) or not directory.is_absolute():
            raise RunClockError("ledger directory must be an absolute Path")
        if type(binding) is not RunBinding:
            raise RunClockError("invalid run binding")
        cls._secure_directory(directory)
        db_path = directory / DB_NAME
        cls._secure_database_file(db_path, require_database=require_database)
        return cls(directory, binding, clock or _SystemClock())

    @staticmethod
    def _secure_directory(directory: Path) -> None:
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise RunClockError("cannot create ledger directory") from exc
        try:
            info = directory.lstat()
        except OSError as exc:
            raise RunClockError("invalid ledger directory") from exc
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise RunClockError("invalid ledger directory")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise RunClockError("invalid ledger directory owner")
        if stat.S_IMODE(info.st_mode) != 0o700:
            raise RunClockError("invalid ledger directory mode")

    @staticmethod
    def _secure_database_file(db_path: Path, *, require_database: bool) -> None:
        flags = os.O_RDWR | os.O_NOFOLLOW
        try:
            descriptor = os.open(db_path, flags)
        except FileNotFoundError:
            if require_database:
                raise RunClockError("run ledger does not exist") from None
            try:
                descriptor = os.open(db_path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            except OSError as exc:
                raise RunClockError("cannot create run ledger") from exc
        except OSError as exc:
            raise RunClockError("invalid run ledger") from exc
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise RunClockError("invalid run ledger")
            if hasattr(os, "getuid") and info.st_uid != os.getuid():
                raise RunClockError("invalid run ledger owner")
            if stat.S_IMODE(info.st_mode) != 0o600:
                raise RunClockError("invalid run ledger mode")
        finally:
            os.close(descriptor)

    def _connect(self) -> sqlite3.Connection:
        self._secure_directory(self._directory)
        self._secure_database_file(self._db_path, require_database=True)
        connection = sqlite3.connect(self._db_path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _transaction(self):
        class _Transaction:
            def __init__(inner, owner: "D4RunClock") -> None:
                inner.owner = owner
                inner.connection: sqlite3.Connection | None = None

            def __enter__(inner) -> sqlite3.Connection:
                try:
                    inner.connection = inner.owner._connect()
                    inner.connection.execute("BEGIN IMMEDIATE")
                    return inner.connection
                except (sqlite3.Error, OSError) as exc:
                    if inner.connection is not None:
                        inner.connection.close()
                    raise RunClockError("run ledger transaction failed") from exc

            def __exit__(inner, exc_type, exc, traceback) -> bool:
                assert inner.connection is not None
                try:
                    if exc_type is None:
                        inner.connection.commit()
                    else:
                        inner.connection.rollback()
                except sqlite3.Error as db_exc:
                    raise RunClockError("run ledger transaction failed") from db_exc
                finally:
                    inner.connection.close()
                if exc_type is not None and issubclass(exc_type, sqlite3.Error):
                    raise RunClockError("run ledger transaction failed") from exc
                return False

        return _Transaction(self)

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                chapter_sha256 TEXT NOT NULL,
                start_sha256 TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                objective_sha256 TEXT NOT NULL,
                profile TEXT NOT NULL,
                boot_id TEXT NOT NULL,
                started_utc TEXT NOT NULL,
                started_mono INTEGER NOT NULL,
                last_sample_utc TEXT NOT NULL,
                last_sample_mono INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS spans (
                span_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                actor TEXT NOT NULL,
                phase TEXT NOT NULL,
                operation TEXT NOT NULL,
                input_hashes TEXT NOT NULL,
                retry_of TEXT REFERENCES spans(span_id),
                started_utc TEXT NOT NULL,
                started_mono INTEGER NOT NULL,
                ended_utc TEXT,
                ended_mono INTEGER,
                outcome TEXT,
                output_hashes TEXT
            )
            """
        )
        run_columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
        if "last_sample_utc" not in run_columns:
            connection.execute("ALTER TABLE runs ADD COLUMN last_sample_utc TEXT")
        if "last_sample_mono" not in run_columns:
            connection.execute("ALTER TABLE runs ADD COLUMN last_sample_mono INTEGER")
        connection.execute(
            """UPDATE runs
               SET last_sample_utc = COALESCE(last_sample_utc, started_utc),
                   last_sample_mono = COALESCE(last_sample_mono, started_mono)
               WHERE last_sample_utc IS NULL OR last_sample_mono IS NULL"""
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS spans_run_started_idx
                ON spans(run_id, started_mono, span_id)
            """
        )

    def _raw_sample(self) -> _Sample:
        try:
            utc = _utc_text(self._clock.utc_now())
            monotonic = self._clock.monotonic_ns()
            boot_id = self._clock.boot_id()
        except RunClockError:
            raise
        except Exception as exc:
            raise RunClockError("clock sampling failed") from exc
        if type(monotonic) is not int or monotonic < 0:
            raise RunClockError("invalid clock sample")
        if type(boot_id) is not str or not BOOT_ID_RE.fullmatch(boot_id):
            raise RunClockError("invalid clock sample")
        return _Sample(utc=utc, monotonic_ns=monotonic, boot_id=boot_id)

    def _run_row(self, connection: sqlite3.Connection) -> sqlite3.Row:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (self._binding.run_id,)).fetchone()
        if row is None:
            raise RunClockError("run does not exist")
        expected = (
            self._binding.chapter_sha256,
            self._binding.start_sha256,
            self._binding.manifest_sha256,
            self._binding.objective_sha256,
            self._binding.profile,
        )
        actual = (
            row["chapter_sha256"],
            row["start_sha256"],
            row["manifest_sha256"],
            row["objective_sha256"],
            row["profile"],
        )
        if actual != expected:
            raise RunClockError("run binding mismatch")
        return row

    def _verified_sample(self, connection: sqlite3.Connection) -> tuple[sqlite3.Row, _Sample]:
        row = self._run_row(connection)
        sample = self._raw_sample()
        if sample.boot_id != row["boot_id"]:
            raise RunClockError("boot ID changed")
        event_mono, event_utc = connection.execute(
            """SELECT MAX(mono), MAX(utc) FROM (
                SELECT started_mono AS mono, started_utc AS utc FROM runs WHERE run_id = ?
                UNION ALL SELECT started_mono, started_utc FROM spans WHERE run_id = ?
                UNION ALL SELECT ended_mono, ended_utc FROM spans
                    WHERE run_id = ? AND ended_mono IS NOT NULL
            )""",
            (self._binding.run_id, self._binding.run_id, self._binding.run_id),
        ).fetchone()
        if type(row["last_sample_mono"]) is not int or type(row["last_sample_utc"]) is not str:
            raise RunClockError("invalid persisted clock sample")
        last_mono = max(row["last_sample_mono"], event_mono)
        last_utc = max(row["last_sample_utc"], event_utc)
        if sample.monotonic_ns < last_mono or sample.utc < last_utc:
            raise RunClockError("clock moved backwards")
        connection.execute(
            "UPDATE runs SET last_sample_utc = ?, last_sample_mono = ? WHERE run_id = ?",
            (sample.utc, sample.monotonic_ns, self._binding.run_id),
        )
        return row, sample

    def begin_span(
        self,
        *,
        actor: str,
        phase: str,
        operation: str,
        input_hashes: dict[str, str],
        retry_of: str | None = None,
    ) -> str:
        actor = _validate_safe_id(actor, "actor")
        operation = _validate_safe_id(operation, "operation")
        if type(phase) is not str or phase not in PHASES:
            raise RunClockError("invalid phase")
        _, encoded_inputs = _validate_hashes(input_hashes, "input hashes")
        if retry_of is not None:
            retry_of = _validate_span_id(retry_of, "retry span ID")
        with self._transaction() as connection:
            _, sample = self._verified_sample(connection)
            if retry_of is not None:
                parent = connection.execute(
                    "SELECT outcome, ended_mono FROM spans WHERE run_id = ? AND span_id = ?",
                    (self._binding.run_id, retry_of),
                ).fetchone()
                if parent is None:
                    raise RunClockError("retry parent does not exist")
                if parent[1] is None or parent[0] != "failed":
                    raise RunClockError("retry parent must be an ended failed span")
            for _ in range(3):
                span_id = secrets.token_hex(16)
                try:
                    connection.execute(
                        """INSERT INTO spans (
                            span_id, run_id, actor, phase, operation, input_hashes,
                            retry_of, started_utc, started_mono
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            span_id,
                            self._binding.run_id,
                            actor,
                            phase,
                            operation,
                            encoded_inputs,
                            retry_of,
                            sample.utc,
                            sample.monotonic_ns,
                        ),
                    )
                    return span_id
                except sqlite3.IntegrityError:
                    continue
            raise RunClockError("cannot allocate span ID")

    def finish_span(
        self,
        *,
        span_id: str,
        outcome: str,
        output_hashes: dict[str, str],
    ) -> None:
        span_id = _validate_span_id(span_id)
        if type(outcome) is not str or outcome not in OUTCOMES:
            raise RunClockError("invalid span outcome")
        _, encoded_outputs = _validate_hashes(output_hashes, "output hashes")
        with self._transaction() as connection:
            _, sample = self._verified_sample(connection)
            span = connection.execute(
                "SELECT ended_mono FROM spans WHERE run_id = ? AND span_id = ?",
                (self._binding.run_id, span_id),
            ).fetchone()
            if span is None:
                raise RunClockError("span does not exist")
            if span[0] is not None:
                raise RunClockError("span already finished")
            connection.execute(
                """UPDATE spans SET ended_utc = ?, ended_mono = ?, outcome = ?, output_hashes = ?
                   WHERE run_id = ? AND span_id = ? AND ended_mono IS NULL""",
                (
                    sample.utc,
                    sample.monotonic_ns,
                    outcome,
                    encoded_outputs,
                    self._binding.run_id,
                    span_id,
                ),
            )

    def summarize(self) -> dict[str, object]:
        with self._transaction() as connection:
            run, observed = self._verified_sample(connection)
            rows = connection.execute(
                "SELECT * FROM spans WHERE run_id = ? ORDER BY started_mono, span_id",
                (self._binding.run_id,),
            ).fetchall()
            spans = []
            unfinished = []
            retries = []
            per_actor: dict[str, int] = {}
            per_phase: dict[str, int] = {}
            for row in rows:
                is_open = row["ended_mono"] is None
                end_mono = observed.monotonic_ns if is_open else row["ended_mono"]
                elapsed = end_mono - row["started_mono"]
                if elapsed < 0:
                    raise RunClockError("clock moved backwards")
                status = "OPEN" if is_open else row["outcome"]
                output_hashes = None if is_open else json.loads(row["output_hashes"])
                item = {
                    "span_id": row["span_id"],
                    "actor": row["actor"],
                    "phase": row["phase"],
                    "operation": row["operation"],
                    "input_hashes": json.loads(row["input_hashes"]),
                    "retry_of": row["retry_of"],
                    "started_at_utc": row["started_utc"],
                    "ended_at_utc": None if is_open else row["ended_utc"],
                    "elapsed_ns": elapsed,
                    "outcome": status,
                    "output_hashes": output_hashes,
                }
                spans.append(item)
                per_actor[row["actor"]] = per_actor.get(row["actor"], 0) + elapsed
                per_phase[row["phase"]] = per_phase.get(row["phase"], 0) + elapsed
                if is_open:
                    unfinished.append(row["span_id"])
                if row["retry_of"] is not None:
                    retries.append({"span_id": row["span_id"], "retry_of": row["retry_of"]})

            run_elapsed = observed.monotonic_ns - run["started_mono"]
            if run_elapsed < 0:
                raise RunClockError("clock moved backwards")
            return {
                "version": 1,
                "status": "OPEN",
                "binding": {
                    "run_id": self._binding.run_id,
                    "chapter_sha256": self._binding.chapter_sha256,
                    "start_sha256": self._binding.start_sha256,
                    "manifest_sha256": self._binding.manifest_sha256,
                    "objective_sha256": self._binding.objective_sha256,
                    "profile": self._binding.profile,
                },
                "started_at_utc": run["started_utc"],
                "observed_at_utc": observed.utc,
                "run_elapsed_ns": run_elapsed,
                "spans": spans,
                "unfinished_span_ids": unfinished,
                "retries": retries,
                "per_actor_span_wall_ns_possibly_overlapping": per_actor,
                "per_phase_span_wall_ns_possibly_overlapping": per_phase,
                "span_wall_totals_may_overlap": True,
                "span_wall_totals_are_not_run_elapsed": True,
                "model_wall_is_not_active_or_token_time": True,
                "human_active_ns": None,
                "active_time_measured": False,
                "formal_g6_pass": False,
                "formal_d4_complete": False,
            }
