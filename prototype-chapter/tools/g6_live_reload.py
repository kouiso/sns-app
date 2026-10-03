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
DEFAULT_PROFILE: Final = "sdk54"
SDK57_PROFILE: Final = "sdk57"
COMMIT_MESSAGE: Final = "文字と色の変更を確かめる"
START_COMMIT_MESSAGE: Final = "最初の画面を作る"
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


@dataclass(frozen=True)
class ExecutionProfile:
    profile_id: str
    chapter_sha256: str
    start_files: tuple[tuple[str, str], ...]
    final_app_sha256: str
    require_initial_commit: bool = False


SDK54_EXECUTION_PROFILE: Final = ExecutionProfile(
    profile_id=DEFAULT_PROFILE,
    chapter_sha256=CHAPTER_SHA256,
    start_files=(("App.tsx", START_APP_SHA256),),
    final_app_sha256=FINAL_APP_SHA256,
)
SDK57_EXECUTION_PROFILE: Final = ExecutionProfile(
    profile_id=SDK57_PROFILE,
    chapter_sha256=("a7c09d267dc001812c96495a349cca129c1fc2f8e48b693119b170507016dc74"),
    start_files=(
        (
            ".gitignore",
            "5936b94a73a28b6735de672b54c2c058a33c9ae1edb62d87d6a4418e14447805",
        ),
        ("App.tsx", START_APP_SHA256),
        ("LICENSE", "fb3ca4a837f5779e83cef89b78253a8949cfb9429c340309f62d0465ec6610b4"),
        (
            "app.json",
            "8c84324e2e1650a62a2b592a2e0b36668ec37965b02ae63dcfd12cdee9cd5be4",
        ),
        (
            "assets/android-icon-background.png",
            "fb139c2dee362ebf2070e23b96da6fc0d43f8492de38b8af1fd7223e19b5861d",
        ),
        (
            "assets/android-icon-foreground.png",
            "9e3d0315a33c6799de601dd34cd8bf8cc3a8d16f3bf75592baec2ceb7240b391",
        ),
        (
            "assets/android-icon-monochrome.png",
            "6371fc2c12e33ad2215a86c281db3d682a81bebe7c957a842c13b8bf00cceb83",
        ),
        (
            "assets/favicon.png",
            "a4e030697a7571b3e95d31860e4da55d2f98e5e861e2b55e414f45a8556828ba",
        ),
        (
            "assets/icon.png",
            "119462bb78eb240a65c869fc067ee599639b3cb5a41953f25c07b17d2a8c7e0f",
        ),
        (
            "assets/splash-icon.png",
            "5f4c0a732b6325bf4071d9124d2ae67e037cb24fcc9c482ef82bea742109a3b8",
        ),
        (
            "index.ts",
            "5c157f4d44972d9c84415e1e4bda595b3abcd8cf733f8a9cd20935bec3eccc42",
        ),
        (
            "package-lock.json",
            "ceaef42805134421829a322d114e5b12d46c6c450d2a4d8de2ee246bb357131d",
        ),
        (
            "package.json",
            "fa499830a8bf57bf29aadeab3261371684046ef496761b2add2e8271a511bc32",
        ),
        (
            "tsconfig.json",
            "712583ff9cdb4b4e4f9b000a4a56d68db8dc1921cbfbc36d490a3a9f2be3dd72",
        ),
    ),
    final_app_sha256=FINAL_APP_SHA256,
    require_initial_commit=True,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _snapshot_digest(files: dict[str, bytes]) -> str:
    return _sha256(
        _canonical(
            [
                {"path": path, "sha256": _sha256(data)}
                for path, data in sorted(files.items())
            ]
        )
    )


def _read_regular(path: Path, label: str) -> bytes:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise LiveReloadError(f"{label} is unavailable") from exc
    if not stat.S_ISREG(mode):
        raise LiveReloadError(f"{label} must be a regular, non-symlink file")
    return path.read_bytes()


def _read_fixed_source_tree(
    root: Path,
    expected_files: tuple[tuple[str, str], ...],
    *,
    require_git: bool,
) -> dict[str, bytes]:
    """Read an exact regular-file tree without following links.

    ``.git`` is controller state rather than source.  A session requires that
    directory, while the pure source validator can be exercised without it.
    """
    if root.is_symlink() or not root.is_dir():
        raise LiveReloadError("start_root must be a non-symlink directory")
    git_path = root / ".git"
    if require_git:
        if git_path.is_symlink() or not git_path.is_dir():
            raise LiveReloadError("start_root must contain a regular .git directory")
    elif git_path.exists() or git_path.is_symlink():
        raise LiveReloadError("source tree must not contain .git")

    expected = dict(expected_files)
    if len(expected) != len(expected_files):
        raise LiveReloadError("execution profile contains duplicate start paths")
    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if relative.parts[0] == ".git":
            continue
        mode = path.lstat().st_mode
        relative_text = relative.as_posix()
        if stat.S_ISLNK(mode):
            raise LiveReloadError(
                f"symlink is forbidden in start source: {relative_text}"
            )
        if stat.S_ISDIR(mode):
            actual_dirs.add(relative_text)
        elif stat.S_ISREG(mode):
            actual_files.add(relative_text)
        else:
            raise LiveReloadError(f"unsupported start source entry: {relative_text}")
    expected_paths = set(expected)
    expected_dirs = {
        Path(path).parent.as_posix()
        for path in expected_paths
        if Path(path).parent.as_posix() != "."
    }
    expected_dirs |= {
        parent.as_posix()
        for path in expected_paths
        for parent in Path(path).parents
        if parent.as_posix() != "."
    }
    if actual_files != expected_paths or actual_dirs != expected_dirs:
        raise LiveReloadError(
            "start source must contain exactly the fixed profile: "
            f"missing_files={sorted(expected_paths - actual_files)} "
            f"extra_files={sorted(actual_files - expected_paths)} "
            f"missing_dirs={sorted(expected_dirs - actual_dirs)} "
            f"extra_dirs={sorted(actual_dirs - expected_dirs)}"
        )
    result: dict[str, bytes] = {}
    for relative_name, expected_sha256 in expected_files:
        data = _read_regular(root / relative_name, f"start source {relative_name}")
        if _sha256(data) != expected_sha256:
            if relative_name == "App.tsx":
                raise LiveReloadError("start App.tsx hash mismatch")
            raise LiveReloadError(f"start source hash mismatch: {relative_name}")
        result[relative_name] = data
    return result


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


def compile_sdk57_plan(
    chapter_path: Path,
    start_app: bytes,
    profile: ExecutionProfile,
) -> tuple[list[Operation], bytes]:
    """Compile the reviewed SDK57 chapter's artifact/Git-only subsequence."""
    chapter = _read_regular(chapter_path, "chapter")
    if _sha256(chapter) != profile.chapter_sha256:
        raise LiveReloadError(
            "SDK57 chapter revision is stale or unapproved for this component"
        )
    if _sha256(start_app) != dict(profile.start_files)["App.tsx"]:
        raise LiveReloadError("start App.tsx hash mismatch")
    try:
        lines = chapter.decode("utf-8").splitlines(keepends=True)
        start_app.decode("utf-8")
    except UnicodeError as exc:
        raise LiveReloadError("chapter and App.tsx must be UTF-8") from exc
    fences = _fences(lines)
    expected_languages = [
        "text",
        "bash",
        "bash",
        "tsx",
        "tsx",
        "bash",
        "bash",
        "bash",
        "bash",
    ]
    if [item[0] for item in fences] != expected_languages:
        raise LiveReloadError(
            "SDK57 chapter fence structure differs from the fixed plan"
        )
    (
        map_fence,
        start_check,
        metro,
        function_fence,
        style_fence,
        save_check_git,
        save_commit_git,
        dirty_git,
        restore_git,
    ) = fences
    if map_fence[3].splitlines() != [
        "[開始画面: 今回もここ] → [投稿作成] → [タイムライン] → [プロフィール]",
        "        └─ 保存した文字と色の反映を確認",
    ]:
        raise LiveReloadError("SDK57 chapter map differs from the reviewed text")
    if start_check[3].splitlines() != [
        'cd "$HOME/sns-course-work/my-sns-sdk57"',
        "pwd",
        "git log -1 --format=%s",
        "git ls-files",
        "git status --short",
    ]:
        raise LiveReloadError("SDK57 start checks differ from the reviewed chapter")
    if metro[3].splitlines() != [
        'cd "$HOME/sns-course-work/my-sns-sdk57" &&',
        "test -x node_modules/.bin/expo &&",
        "npx --no-install expo start --port 8090",
    ]:
        raise LiveReloadError("SDK57 Metro commands differ from the reviewed chapter")
    save_check_commands = save_check_git[3].splitlines()
    save_commit_commands = save_commit_git[3].splitlines()
    dirty_commands = dirty_git[3].splitlines()
    restore_commands = restore_git[3].splitlines()
    if save_check_commands != [
        'cd "$HOME/sns-course-work/my-sns-sdk57"',
        "git status --short App.tsx",
        "git diff -- App.tsx",
    ] or save_commit_commands != [
        "git add App.tsx",
        f'git commit -m "{COMMIT_MESSAGE}"',
        "git log -1 --format=%s",
        "git status --short",
    ]:
        raise LiveReloadError("SDK57 save commands differ from the reviewed chapter")
    if dirty_commands != [
        "git status --short App.tsx",
        "git diff -- App.tsx",
    ] or restore_commands != [
        "git restore App.tsx",
        "git diff -- App.tsx",
        "git status --short",
    ]:
        raise LiveReloadError("SDK57 restore commands differ from the reviewed chapter")

    reviewed_function = function_fence[3].rstrip("\n")
    final_app = (
        reviewed_function + "\n\n" + style_fence[3].rstrip("\n") + "\n"
    ).encode("utf-8")
    if _sha256(final_app) != profile.final_app_sha256:
        raise LiveReloadError(
            "compiled SDK57 App.tsx differs from the reviewed listing"
        )
    if final_app == start_app:
        raise LiveReloadError("SDK57 complete App.tsx edit is a no-op")
    final_text = final_app.decode("utf-8")
    if final_text.count("いま書き換えたところが、すぐここに出ます") != 1:
        raise LiveReloadError("restore-practice text anchor is not unique")
    practice_app = final_text.replace(
        "いま書き換えたところが、すぐここに出ます",
        RESTORE_PRACTICE_TEXT,
        1,
    ).encode("utf-8")
    practice_lines = [
        number
        for number, line in enumerate(lines, 1)
        if "3つ目の `<Text>` の文を「元に戻す練習」に変え" in line
    ]
    if len(practice_lines) != 1:
        raise LiveReloadError("SDK57 restore-practice instruction is not unique")

    complete_app_source = _source_binding(lines, function_fence[1], style_fence[2])
    save_check_sources = [
        _source_binding(
            lines,
            save_check_git[1] + index,
            save_check_git[1] + index,
        )
        for index in range(len(save_check_commands))
    ]
    save_commit_sources = [
        _source_binding(
            lines,
            save_commit_git[1] + index,
            save_commit_git[1] + index,
        )
        for index in range(len(save_commit_commands))
    ]
    dirty_sources = [
        _source_binding(lines, dirty_git[1] + index, dirty_git[1] + index)
        for index in range(len(dirty_commands))
    ]
    restore_sources = [
        _source_binding(lines, restore_git[1] + index, restore_git[1] + index)
        for index in range(len(restore_commands))
    ]
    practice_source = _source_binding(lines, practice_lines[0], practice_lines[0])
    return (
        [
            Operation(
                "write-complete-app",
                "write",
                complete_app_source,
                content=final_app,
                phase="complete-edit",
            ),
            Operation(
                "git-status-before-commit",
                "command",
                save_check_sources[1],
                argv=("/usr/bin/git", "status", "--short", "App.tsx"),
            ),
            Operation(
                "git-diff-before-commit",
                "command",
                save_check_sources[2],
                argv=("/usr/bin/git", "diff", "--", "App.tsx"),
            ),
            Operation(
                "git-add-app",
                "command",
                save_commit_sources[0],
                argv=("/usr/bin/git", "add", "App.tsx"),
            ),
            Operation(
                "git-commit-app",
                "command",
                save_commit_sources[1],
                argv=("/usr/bin/git", "commit", "-m", COMMIT_MESSAGE),
                phase="committed",
            ),
            Operation(
                "git-log-after-commit",
                "command",
                save_commit_sources[2],
                argv=("/usr/bin/git", "log", "-1", "--format=%s"),
            ),
            Operation(
                "git-status-after-commit",
                "command",
                save_commit_sources[3],
                argv=("/usr/bin/git", "status", "--short"),
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
                dirty_sources[0],
                argv=("/usr/bin/git", "status", "--short", "App.tsx"),
            ),
            Operation(
                "git-diff-before-restore",
                "command",
                dirty_sources[1],
                argv=("/usr/bin/git", "diff", "--", "App.tsx"),
            ),
            Operation(
                "git-restore-app",
                "command",
                restore_sources[0],
                argv=("/usr/bin/git", "restore", "App.tsx"),
            ),
            Operation(
                "git-diff-after-restore",
                "command",
                restore_sources[1],
                argv=("/usr/bin/git", "diff", "--", "App.tsx"),
                phase="git-restored",
            ),
            Operation(
                "git-status-after-restore",
                "command",
                restore_sources[2],
                argv=("/usr/bin/git", "status", "--short"),
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


def _execution_profile(profile_id: str) -> ExecutionProfile:
    if type(profile_id) is not str:
        raise LiveReloadError(f"unknown fixed execution profile: {profile_id!r}")
    profiles = {
        DEFAULT_PROFILE: SDK54_EXECUTION_PROFILE,
        SDK57_PROFILE: SDK57_EXECUTION_PROFILE,
    }
    try:
        return profiles[profile_id]
    except KeyError as exc:
        raise LiveReloadError(
            f"unknown fixed execution profile: {profile_id!r}"
        ) from exc


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
        *,
        profile: str = DEFAULT_PROFILE,
    ) -> None:
        self.profile = _execution_profile(profile)
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
        start_files = _read_fixed_source_tree(
            start_root, self.profile.start_files, require_git=True
        )
        start_app = start_files["App.tsx"]
        if self.profile.profile_id == DEFAULT_PROFILE:
            self.operations, self.chapter = compile_plan(chapter_path, start_app)
        elif self.profile.profile_id == SDK57_PROFILE:
            self.operations, self.chapter = compile_sdk57_plan(
                chapter_path, start_app, self.profile
            )
        else:  # pragma: no cover - _execution_profile is the closed selector.
            raise LiveReloadError("unsupported fixed execution profile")
        for relative, data in start_files.items():
            destination = workspace / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        shutil.copytree(start_root / ".git", workspace / ".git")
        self.workspace = workspace
        self.evidence_root = evidence_root
        self.start_files = start_files
        self.start_source_snapshot_sha256 = _snapshot_digest(start_files)
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
        expected_paths = sorted(self.start_files)
        if self._git("ls-files", "-v").splitlines() != [
            f"H {path}" for path in expected_paths
        ]:
            raise LiveReloadError("start files must all have normal Git index flags")
        for path in expected_paths:
            if (
                self._git("rev-parse", f"HEAD:{path}").strip()
                != self._git("hash-object", path).strip()
            ):
                raise LiveReloadError(
                    f"start HEAD {path} differs from validated start bytes"
                )
        if self._git("status", "--porcelain", "--untracked-files=all"):
            raise LiveReloadError("start Git repository must be clean")
        if self._git("ls-files").splitlines() != expected_paths:
            raise LiveReloadError(
                "start Git repository must track exactly the fixed source files"
            )
        self.start_head = self._git("rev-parse", "HEAD").strip()
        if self.profile.require_initial_commit:
            if self._git("rev-list", "--count", self.start_head).strip() != "1":
                raise LiveReloadError("SDK57 start HEAD must be the initial commit")
            if (
                self._git("rev-list", "--parents", "-n", "1", self.start_head).strip()
                != self.start_head
            ):
                raise LiveReloadError("SDK57 start HEAD must have no parent")
            if (
                self._git("log", "-1", "--format=%s", self.start_head).rstrip("\n")
                != START_COMMIT_MESSAGE
            ):
                raise LiveReloadError(
                    "SDK57 start commit message differs from the fixed message"
                )

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
            and _sha256(app) != self.profile.final_app_sha256
        ):
            raise LiveReloadError("style edit did not reach the reviewed App.tsx")
        if (
            operation.operation_id == "write-complete-app"
            and _sha256(app) != self.profile.final_app_sha256
        ):
            raise LiveReloadError("complete edit did not reach the reviewed App.tsx")
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
        if (
            operation.operation_id == "git-log-after-commit"
            and stdout != f"{COMMIT_MESSAGE}\n"
        ):
            raise LiveReloadError("post-commit log differs from the fixed message")
        if operation.operation_id == "git-status-after-commit" and stdout:
            raise LiveReloadError("repository is not clean after the chapter commit")
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
            and _sha256(app) != self.profile.final_app_sha256
        ):
            raise LiveReloadError("git restore did not restore the committed App.tsx")
        if operation.operation_id == "git-diff-after-restore":
            if stdout or self._git("status", "--porcelain", "--untracked-files=all"):
                raise LiveReloadError("repository is not clean after git restore")
        if operation.operation_id == "git-status-after-restore" and stdout:
            raise LiveReloadError("repository is not clean after restore verification")

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
        if _sha256(final_app) != self.profile.final_app_sha256:
            raise LiveReloadError("final App.tsx integrity check failed")
        final_expected = tuple(
            (
                path,
                self.profile.final_app_sha256 if path == "App.tsx" else digest,
            )
            for path, digest in self.profile.start_files
        )
        final_files = _read_fixed_source_tree(
            self.workspace, final_expected, require_git=True
        )
        for path, start_data in self.start_files.items():
            if path != "App.tsx" and final_files[path] != start_data:
                raise LiveReloadError(
                    f"non-App source changed during execution: {path}"
                )
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
        expected_paths = sorted(final_files)
        if (
            self._git("ls-tree", "-r", "--name-only", final_head).splitlines()
            != expected_paths
        ):
            raise LiveReloadError(
                "chapter commit tree differs from the fixed source files"
            )
        for path in expected_paths:
            if (
                self._git("rev-parse", f"{final_head}:{path}").strip()
                != self._git("hash-object", path).strip()
            ):
                raise LiveReloadError(
                    f"chapter commit file differs from workspace: {path}"
                )
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
            "profile": self.profile.profile_id,
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
            "start_app_sha256": _sha256(self.start_files["App.tsx"]),
            "final_app_sha256": _sha256(final_app),
            "start_source_files": [
                {"path": path, "sha256": _sha256(data)}
                for path, data in sorted(self.start_files.items())
            ],
            "start_source_snapshot_sha256": self.start_source_snapshot_sha256,
            "final_source_files": [
                {"path": path, "sha256": _sha256(data)}
                for path, data in sorted(final_files.items())
            ],
            "final_source_snapshot_sha256": _snapshot_digest(final_files),
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
