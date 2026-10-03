"""Non-formal, fixed-operation artifact/Git executor for chapter-live-reload.

The model-facing surface is intentionally only ``LiveReloadSession.request``
with an operation ID.  The trusted controller owns paths and setup.  GUI,
Metro, device UI, model/MCP wiring, and formal G6 completion remain unsupported.
Recorded source hashes bind disk bytes observed at initialization and finish;
they do not prove which bytes the already-running interpreter loaded.
The trusted same-UID controller must prevent path replacement between checks;
this component does not defend against a hostile host process racing its reads.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from g6_broker import (
    BWRAP_PATH,
    _bwrap_prefix,
    _preflight,
    _run,
    _validate_bwrap,
)


class LiveReloadError(ValueError):
    """Raised when the fixed chapter execution cannot be proven."""


CHAPTER_SHA256: Final = (
    "2df26dc8ba13d0928187ae81b5f2c1af6a55e1a5ec91d600480387f8fca67785"
)
START_APP_SHA256: Final = (
    "5c7d8b989dc7a6a70e4a6be61ec95b1c5a1562e8a510efb3aa6b8cbe94033190"
)
FINAL_APP_SHA256: Final = (
    "fb927c6ef3ec31a6c6237f1e9454d7147bdb0605314edc7e0faa7efb504a4949"
)
COMMIT_MESSAGE: Final = "文字と色の変更を確かめる"
RESTORE_PRACTICE_TEXT: Final = "元に戻す練習"
COMPONENT_SOURCE: Final = Path(__file__).resolve()
BROKER_SOURCE: Final = COMPONENT_SOURCE.with_name("g6_broker.py")


@dataclass(frozen=True)
class SourceBinding:
    start_line: int
    end_line: int
    sha256: str


@dataclass(frozen=True)
class Operation:
    operation_id: str
    kind: str
    source: SourceBinding
    argv: tuple[str, ...] = ()
    content: bytes | None = None
    phase: str | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _read_regular(path: Path, label: str) -> bytes:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise LiveReloadError(f"{label} is unavailable") from exc
    if not stat.S_ISREG(mode):
        raise LiveReloadError(f"{label} must be a regular, non-symlink file")
    return path.read_bytes()


def _source_binding(lines: list[str], start: int, end: int) -> SourceBinding:
    data = "".join(lines[start - 1 : end]).encode("utf-8")
    return SourceBinding(start, end, _sha256(data))


def _fences(lines: list[str]) -> list[tuple[str, int, int, str]]:
    result: list[tuple[str, int, int, str]] = []
    language: str | None = None
    start = 0
    body: list[str] = []
    for line_number, line in enumerate(lines, 1):
        if line.startswith("```"):
            if language is None:
                language = line[3:].strip()
                start = line_number + 1
                body = []
            else:
                result.append((language, start, line_number - 1, "".join(body)))
                language = None
        elif language is not None:
            body.append(line)
    if language is not None:
        raise LiveReloadError("chapter contains an unclosed fence")
    return result


def compile_plan(chapter_path: Path, start_app: bytes) -> tuple[list[Operation], bytes]:
    """Compile the one accepted chapter revision into fixed operations."""
    if chapter_path.is_symlink() or not chapter_path.is_file():
        raise LiveReloadError("chapter must be a regular, non-symlink file")
    chapter = chapter_path.read_bytes()
    if _sha256(chapter) != CHAPTER_SHA256:
        raise LiveReloadError(
            "chapter revision is stale or unapproved for this component"
        )
    if _sha256(start_app) != START_APP_SHA256:
        raise LiveReloadError("start App.tsx hash mismatch")
    try:
        lines = chapter.decode("utf-8").splitlines(keepends=True)
        start_text = start_app.decode("utf-8")
    except UnicodeError as exc:
        raise LiveReloadError("chapter and App.tsx must be UTF-8") from exc
    fences = _fences(lines)
    expected_languages = ["bash", "tsx", "tsx", "bash", "bash"]
    if [item[0] for item in fences] != expected_languages:
        raise LiveReloadError("chapter fence structure differs from the fixed plan")
    first_bash, function_fence, style_fence, save_git, restore_git = fences
    if first_bash[3].splitlines() != ["code App.tsx", "npx expo start --port 8090"]:
        raise LiveReloadError("editor/Metro commands differ from the reviewed chapter")
    save_commands = save_git[3].splitlines()
    restore_commands = restore_git[3].splitlines()
    if save_commands != [
        "git status --short App.tsx",
        "git diff -- App.tsx",
        "git add App.tsx",
        f'git commit -m "{COMMIT_MESSAGE}"',
    ] or restore_commands != [
        "git status --short App.tsx",
        "git diff -- App.tsx",
        "git restore App.tsx",
        "git diff -- App.tsx",
    ]:
        raise LiveReloadError("Git commands differ from the reviewed chapter")

    function_start = start_text.index("export default function App()")
    function_end = start_text.index("\n\nconst styles", function_start)
    function_stage = (
        start_text[:function_start]
        + function_fence[3].rstrip("\n")
        + start_text[function_end:]
    )
    style_anchor = (
        "  body: {\n    fontSize: 16,\n    marginTop: 8,\n    color: '#555',\n  },\n"
    )
    if function_stage.count(style_anchor) != 1:
        raise LiveReloadError("start App.tsx style anchor is not unique")
    final_text = function_stage.replace(style_anchor, style_anchor + style_fence[3], 1)
    final_app = final_text.encode("utf-8")
    if _sha256(final_app) != FINAL_APP_SHA256:
        raise LiveReloadError("compiled App.tsx differs from the reviewed listing")
    if final_text.count("いま書き換えたところが、すぐここに出ます") != 1:
        raise LiveReloadError("restore-practice text anchor is not unique")
    practice_app = final_text.replace(
        "いま書き換えたところが、すぐここに出ます",
        RESTORE_PRACTICE_TEXT,
        1,
    ).encode("utf-8")

    if len(lines) < 83 or RESTORE_PRACTICE_TEXT not in lines[82]:
        raise LiveReloadError("restore-practice instruction is missing from line 83")

    function_source = _source_binding(lines, function_fence[1], function_fence[2])
    style_source = _source_binding(lines, style_fence[1], style_fence[2])
    save_sources = [
        _source_binding(lines, save_git[1] + index, save_git[1] + index)
        for index in range(4)
    ]
    restore_sources = [
        _source_binding(lines, restore_git[1] + index, restore_git[1] + index)
        for index in range(4)
    ]
    practice_source = _source_binding(lines, 83, 83)
    return (
        [
            Operation(
                "write-app-function",
                "write",
                function_source,
                content=function_stage.encode(),
                phase="text",
            ),
            Operation(
                "write-note-style",
                "write",
                style_source,
                content=final_app,
                phase="style",
            ),
            Operation(
                "git-status-before-commit",
                "command",
                save_sources[0],
                argv=("/usr/bin/git", "status", "--short", "App.tsx"),
            ),
            Operation(
                "git-diff-before-commit",
                "command",
                save_sources[1],
                argv=("/usr/bin/git", "diff", "--", "App.tsx"),
            ),
            Operation(
                "git-add-app",
                "command",
                save_sources[2],
                argv=("/usr/bin/git", "add", "App.tsx"),
            ),
            Operation(
                "git-commit-app",
                "command",
                save_sources[3],
                argv=("/usr/bin/git", "commit", "-m", COMMIT_MESSAGE),
                phase="committed",
            ),
            Operation(
                "write-restore-practice",
                "write",
                practice_source,
                content=practice_app,
                phase="restore-practice-dirty",
            ),
            Operation(
                "git-status-before-restore",
                "command",
                restore_sources[0],
                argv=("/usr/bin/git", "status", "--short", "App.tsx"),
            ),
            Operation(
                "git-diff-before-restore",
                "command",
                restore_sources[1],
                argv=("/usr/bin/git", "diff", "--", "App.tsx"),
            ),
            Operation(
                "git-restore-app",
                "command",
                restore_sources[2],
                argv=("/usr/bin/git", "restore", "App.tsx"),
            ),
            Operation(
                "git-diff-after-restore",
                "command",
                restore_sources[3],
                argv=("/usr/bin/git", "diff", "--", "App.tsx"),
                phase="git-restored",
            ),
        ],
        chapter,
    )


def _validate_tree_no_links(root: Path, label: str) -> None:
    if root.is_symlink() or not root.is_dir():
        raise LiveReloadError(f"{label} must be a non-symlink directory")
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise LiveReloadError(
                f"unsupported {label} entry: {path.relative_to(root)}"
            )


class LiveReloadSession:
    """Execute the fixed artifact/Git subsequence one requested ID at a time.

    An initialization failure preserves any copied workspace/evidence for
    diagnosis.  That path set is consumed; a retry must use new empty paths.
    """

    def __init__(
        self,
        chapter_path: Path,
        start_root: Path,
        workspace: Path,
        evidence_root: Path,
    ) -> None:
        for root, label in (
            (start_root, "start_root"),
            (workspace, "workspace"),
            (evidence_root, "evidence_root"),
        ):
            if root.is_symlink() or not root.is_dir():
                raise LiveReloadError(f"{label} must be a non-symlink directory")
        resolved = {
            "start_root": start_root.resolve(),
            "workspace": workspace.resolve(),
            "evidence_root": evidence_root.resolve(),
        }
        names = list(resolved)
        for index, name in enumerate(names):
            for other_name in names[index + 1 :]:
                root = resolved[name]
                other = resolved[other_name]
                if root.is_relative_to(other) or other.is_relative_to(root):
                    raise LiveReloadError(f"{name} and {other_name} must not overlap")
        for root, label in ((workspace, "workspace"), (evidence_root, "evidence_root")):
            if any(root.iterdir()):
                raise LiveReloadError(f"{label} must be empty")
        _validate_tree_no_links(start_root, "start_root")
        if {path.name for path in start_root.iterdir()} != {"App.tsx", ".git"}:
            raise LiveReloadError("start_root must contain exactly App.tsx and .git")
        if not (start_root / "App.tsx").is_file() or not (start_root / ".git").is_dir():
            raise LiveReloadError("start_root App.tsx/.git entry types are invalid")
        start_app = _read_regular(start_root / "App.tsx", "start App.tsx")
        self.operations, self.chapter = compile_plan(chapter_path, start_app)
        (workspace / "App.tsx").write_bytes(start_app)
        shutil.copytree(start_root / ".git", workspace / ".git")
        self.workspace = workspace
        self.evidence_root = evidence_root
        self.index = 0
        self.trace: list[dict[str, Any]] = []
        self.start_head = ""
        self.committed_head = ""
        self.closed = False
        self.failed = False
        self.failure_reason = ""
        self.finalized = False
        self.component_source_sha256 = _sha256(
            _read_regular(COMPONENT_SOURCE, "component source")
        )
        self.broker_source_sha256 = _sha256(
            _read_regular(BROKER_SOURCE, "broker source")
        )
        self.private_home = workspace.parent / f".{workspace.name}-live-reload-home"
        if self.private_home.exists() or self.private_home.is_symlink():
            raise LiveReloadError("private HOME path already exists")
        self.private_home.mkdir(mode=0o700)
        try:
            _validate_bwrap(BWRAP_PATH)
            self.bwrap_sha256 = _sha256(_read_regular(BWRAP_PATH, "bwrap executable"))
            self.prefix = _bwrap_prefix(BWRAP_PATH, workspace, self.private_home) + [
                "--dev",
                "/dev",
            ]
            self.preflight = _preflight(self.prefix)
            self._validate_start()
        except BaseException as exc:
            self.close()
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, LiveReloadError):
                raise
            raise LiveReloadError(str(exc)) from exc

    @property
    def next_operation_id(self) -> str | None:
        if self.closed:
            return None
        return (
            self.operations[self.index].operation_id
            if self.index < len(self.operations)
            else None
        )

    def _command(self, argv: tuple[str, ...]) -> tuple[str, str]:
        result = _run(self.prefix + list(argv))
        if result.returncode != 0:
            raise LiveReloadError(
                f"fixed command failed: {argv[1:]} exit={result.returncode}: "
                f"{result.stderr.strip()}"
            )
        return result.stdout, result.stderr

    def _git(self, *args: str) -> str:
        return self._command(("/usr/bin/git", *args))[0]

    def _validate_start(self) -> None:
        # Inspect hooks and the repository-local config before commands such as
        # status that may honor hook-like settings including core.fsmonitor.
        hooks = self.workspace / ".git" / "hooks"
        if hooks.is_dir() and any(
            path.is_file()
            and not path.name.endswith(".sample")
            and path.stat().st_mode & 0o111
            for path in hooks.iterdir()
        ):
            raise LiveReloadError("executable Git hooks are forbidden")
        if (self.workspace / ".git" / "commondir").exists():
            raise LiveReloadError("Git commondir indirection is forbidden")
        allowed_config = {
            "core.repositoryformatversion",
            "core.filemode",
            "core.bare",
            "core.logallrefupdates",
            "user.name",
            "user.email",
        }
        actual_config = set(
            self._git(
                "config",
                "--no-includes",
                "--file",
                ".git/config",
                "--name-only",
                "--list",
            ).splitlines()
        )
        if not actual_config <= allowed_config:
            raise LiveReloadError(
                "start Git repository contains unsupported local config"
            )
        for key in ("user.name", "user.email"):
            value = self._git(
                "config",
                "--no-includes",
                "--file",
                ".git/config",
                "--get",
                key,
            )
            if not value.strip():
                raise LiveReloadError(f"start Git repository lacks local {key}")
        if self._git("rev-parse", "--show-toplevel").strip() != "/work":
            raise LiveReloadError("start Git repository is not rooted at the workspace")
        if self._git("rev-parse", "--git-common-dir").strip() != ".git":
            raise LiveReloadError("start Git common directory must be .git")
        if self._git("ls-files", "-v").splitlines() != ["H App.tsx"]:
            raise LiveReloadError("start App.tsx must have normal Git index flags")
        if (
            self._git("rev-parse", "HEAD:App.tsx").strip()
            != self._git("hash-object", "App.tsx").strip()
        ):
            raise LiveReloadError(
                "start HEAD App.tsx differs from validated start bytes"
            )
        if self._git("status", "--porcelain", "--untracked-files=all"):
            raise LiveReloadError("start Git repository must be clean")
        if self._git("ls-files").splitlines() != ["App.tsx"]:
            raise LiveReloadError("start Git repository must track only App.tsx")
        self.start_head = self._git("rev-parse", "HEAD").strip()

    def _write(self, content: bytes) -> None:
        encoded = content.hex()
        script = (
            "from pathlib import Path; "
            f"Path('App.tsx').write_bytes(bytes.fromhex('{encoded}'))"
        )
        self._command(("/usr/bin/python3", "-c", script))

    def _snapshot(self, phase: str) -> str:
        phase_root = self.evidence_root / phase
        if phase_root.exists():
            raise LiveReloadError(f"duplicate phase snapshot: {phase}")
        phase_root.mkdir()
        app = _read_regular(self.workspace / "App.tsx", "workspace App.tsx")
        (phase_root / "App.tsx").write_bytes(app)
        status = self._git("status", "--short", "App.tsx")
        head = self._git("rev-parse", "HEAD").strip()
        metadata = {
            "phase": phase,
            "app_sha256": _sha256(app),
            "git_status_sha256": _sha256(status.encode()),
            "head": head,
        }
        metadata_bytes = _canonical(metadata)
        (phase_root / "snapshot.json").write_bytes(metadata_bytes)
        return _sha256(
            _canonical(
                {"app_sha256": _sha256(app), "metadata_sha256": _sha256(metadata_bytes)}
            )
        )

    def request(self, operation_id: str) -> dict[str, Any]:
        if self.closed:
            raise LiveReloadError("session is closed")
        if type(operation_id) is not str or self.index >= len(self.operations):
            raise LiveReloadError(
                "operation request is invalid or execution is complete"
            )
        operation = self.operations[self.index]
        if operation_id != operation.operation_id:
            raise LiveReloadError(
                f"operation order violation: expected {operation.operation_id!r}"
            )
        stdout = ""
        stderr = ""
        try:
            if operation.kind == "write":
                assert operation.content is not None
                self._write(operation.content)
                if (
                    _read_regular(self.workspace / "App.tsx", "workspace App.tsx")
                    != operation.content
                ):
                    raise LiveReloadError(
                        f"write operation did not produce exact bytes: {operation.operation_id}"
                    )
            elif operation.kind == "command":
                stdout, stderr = self._command(operation.argv)
            else:
                raise LiveReloadError(
                    f"unsupported compiled operation kind: {operation.kind}"
                )
            self._validate_operation_effect(operation, stdout)
            phase_snapshot_sha256 = ""
            if operation.phase is not None:
                phase_snapshot_sha256 = self._snapshot(operation.phase)
            record = {
                "id": operation.operation_id,
                "kind": operation.kind,
                "source_start_line": operation.source.start_line,
                "source_end_line": operation.source.end_line,
                "source_sha256": operation.source.sha256,
                "chapter_sha256": _sha256(self.chapter),
                "argv_sha256": _sha256(_canonical(list(operation.argv))),
                "content_sha256": _sha256(operation.content or b""),
                "stdout_sha256": _sha256(stdout.encode()),
                "stderr_sha256": _sha256(stderr.encode()),
                "phase": operation.phase,
                "phase_snapshot_sha256": phase_snapshot_sha256,
            }
            self.trace.append(record)
            self.index += 1
            return record
        except BaseException as exc:
            self.failed = True
            self.failure_reason = str(exc) or type(exc).__name__
            self.close()
            raise

    def _validate_operation_effect(self, operation: Operation, stdout: str) -> None:
        app = _read_regular(self.workspace / "App.tsx", "workspace App.tsx")
        if operation.operation_id == "write-app-function" and _sha256(app) in {
            START_APP_SHA256,
            FINAL_APP_SHA256,
        }:
            raise LiveReloadError(
                "function edit was a no-op or skipped its intermediate stage"
            )
        if (
            operation.operation_id == "write-note-style"
            and _sha256(app) != FINAL_APP_SHA256
        ):
            raise LiveReloadError("style edit did not reach the reviewed App.tsx")
        if (
            operation.operation_id == "git-status-before-commit"
            and stdout != " M App.tsx\n"
        ):
            raise LiveReloadError(
                "pre-commit status did not show only App.tsx modified"
            )
        if operation.operation_id == "git-diff-before-commit" and not stdout:
            raise LiveReloadError("pre-commit diff is empty")
        if operation.operation_id == "git-add-app":
            if self._git("diff", "--cached", "--name-only").splitlines() != ["App.tsx"]:
                raise LiveReloadError("git add staged files other than App.tsx")
        if operation.operation_id == "git-commit-app":
            if self._git("status", "--porcelain", "--untracked-files=all"):
                raise LiveReloadError("repository is not clean after commit")
            self.committed_head = self._git("rev-parse", "HEAD").strip()
            if self.committed_head == self.start_head:
                raise LiveReloadError("git commit did not advance HEAD")
        if operation.operation_id == "write-restore-practice":
            if RESTORE_PRACTICE_TEXT.encode() not in app or not self._git(
                "status", "--short", "App.tsx"
            ):
                raise LiveReloadError(
                    "restore-practice edit did not create a dirty App.tsx"
                )
        if (
            operation.operation_id == "git-status-before-restore"
            and stdout != " M App.tsx\n"
        ):
            raise LiveReloadError("restore status did not show App.tsx modified")
        if (
            operation.operation_id == "git-diff-before-restore"
            and RESTORE_PRACTICE_TEXT not in stdout
        ):
            raise LiveReloadError("restore-practice diff is missing the specified text")
        if (
            operation.operation_id == "git-restore-app"
            and _sha256(app) != FINAL_APP_SHA256
        ):
            raise LiveReloadError("git restore did not restore the committed App.tsx")
        if operation.operation_id == "git-diff-after-restore":
            if stdout or self._git("status", "--porcelain", "--untracked-files=all"):
                raise LiveReloadError("repository is not clean after git restore")

    def finish(self) -> dict[str, Any]:
        if self.closed:
            raise LiveReloadError("session is closed")
        if self.finalized:
            raise LiveReloadError("session receipt was already finalized")
        if self.index != len(self.operations):
            raise LiveReloadError("required operation sequence is incomplete")
        if any(self.private_home.iterdir()):
            raise LiveReloadError(
                "fixed operations wrote unexpected private HOME state"
            )
        if (
            _sha256(_read_regular(COMPONENT_SOURCE, "component source"))
            != self.component_source_sha256
        ):
            raise LiveReloadError("component source changed during execution")
        if (
            _sha256(_read_regular(BROKER_SOURCE, "broker source"))
            != self.broker_source_sha256
        ):
            raise LiveReloadError("broker source changed during execution")
        if _sha256(_read_regular(BWRAP_PATH, "bwrap executable")) != self.bwrap_sha256:
            raise LiveReloadError("bwrap executable changed during execution")
        final_app = _read_regular(self.workspace / "App.tsx", "final App.tsx")
        if _sha256(final_app) != FINAL_APP_SHA256:
            raise LiveReloadError("final App.tsx integrity check failed")
        if self._git("status", "--porcelain", "--untracked-files=all"):
            raise LiveReloadError("final Git repository is not clean")
        final_head = self._git("rev-parse", "HEAD").strip()
        if not self.committed_head or final_head != self.committed_head:
            raise LiveReloadError("final Git HEAD differs from the chapter commit")
        if self._git("rev-list", "--parents", "-n", "1", final_head).splitlines() != [
            f"{final_head} {self.start_head}"
        ]:
            raise LiveReloadError("chapter commit parent differs from the start HEAD")
        if (
            self._git("log", "-1", "--format=%s", final_head).rstrip("\n")
            != COMMIT_MESSAGE
        ):
            raise LiveReloadError(
                "chapter commit message differs from the fixed message"
            )
        if self._git("ls-tree", "--name-only", final_head).splitlines() != ["App.tsx"]:
            raise LiveReloadError("chapter commit tree must contain only App.tsx")
        if (
            self._git("rev-parse", f"{final_head}:App.tsx").strip()
            != self._git("hash-object", "App.tsx").strip()
        ):
            raise LiveReloadError("chapter commit App.tsx differs from final App.tsx")
        expected_phases = {
            operation.phase
            for operation in self.operations
            if operation.phase is not None
        }
        if {path.name for path in self.evidence_root.iterdir()} != expected_phases:
            raise LiveReloadError("evidence root contains unexpected phase entries")
        for record in self.trace:
            phase = record["phase"]
            if phase is None:
                continue
            phase_root = self.evidence_root / phase
            if phase_root.is_symlink() or not phase_root.is_dir():
                raise LiveReloadError(f"phase snapshot directory is invalid: {phase}")
            if {path.name for path in phase_root.iterdir()} != {
                "App.tsx",
                "snapshot.json",
            }:
                raise LiveReloadError(
                    f"phase snapshot contains unexpected entries: {phase}"
                )
            app = _read_regular(phase_root / "App.tsx", f"{phase} App.tsx")
            metadata = _read_regular(
                phase_root / "snapshot.json", f"{phase} snapshot metadata"
            )
            actual_snapshot_sha256 = _sha256(
                _canonical(
                    {
                        "app_sha256": _sha256(app),
                        "metadata_sha256": _sha256(metadata),
                    }
                )
            )
            if actual_snapshot_sha256 != record["phase_snapshot_sha256"]:
                raise LiveReloadError(f"phase snapshot integrity check failed: {phase}")
        receipt = {
            "scope": "G6_LIVE_RELOAD_ARTIFACT_GIT_COMPONENT_NON_FORMAL",
            "claims": {
                "artifact_git_execution": True,
                "formal_g6_exec": False,
                "model_mcp_connected": False,
                "metro_executed": False,
                "ui_validated": False,
            },
            "chapter_sha256": _sha256(self.chapter),
            "operation_plan_sha256": _sha256(
                _canonical(
                    [
                        {
                            "id": operation.operation_id,
                            "kind": operation.kind,
                            "source_sha256": operation.source.sha256,
                            "argv_sha256": _sha256(_canonical(list(operation.argv))),
                            "content_sha256": _sha256(operation.content or b""),
                        }
                        for operation in self.operations
                    ]
                )
            ),
            "bwrap_sha256": self.bwrap_sha256,
            "component_source_sha256": self.component_source_sha256,
            "broker_source_sha256": self.broker_source_sha256,
            "sandbox_recipe_sha256": _sha256(_canonical(self.prefix)),
            "start_app_sha256": START_APP_SHA256,
            "final_app_sha256": _sha256(final_app),
            "start_head": self.start_head,
            "final_head": final_head,
            "preflight": self.preflight,
            "unsupported": [
                "code App.tsx GUI operation",
                "Metro/network runtime",
                "device UI observation",
                "model/MCP adapter",
                "formal G6 verdict",
            ],
            "actions": self.trace,
        }
        output = {"trace": receipt, "trace_sha256": _sha256(_canonical(receipt))}
        (self.evidence_root / "trace.json").write_bytes(_canonical(output))
        self.finalized = True
        return output

    def close(self) -> None:
        self.closed = True
        try:
            self.private_home.rmdir()
        except OSError:
            pass

    def __enter__(self) -> LiveReloadSession:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def run_all(session: LiveReloadSession) -> dict[str, Any]:
    """Trusted-controller helper; not a model or CLI endpoint."""
    while session.next_operation_id is not None:
        session.request(session.next_operation_id)
    return session.finish()
