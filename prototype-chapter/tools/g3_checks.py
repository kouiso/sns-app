#!/usr/bin/env python3
"""G3 のうち textlint 以外の4検査を行う暫定実装。

Phase 2 / P1 / G1 前の検知テスト用であり、正式な G3 通過証拠を作る道具ではない。
開始状態は上流で凍結した manifest を入力に取り、未定義を合格にしない。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence, TypeGuard


MAX_CODE_LINES = 25
MAX_PARAGRAPH_SENTENCES = 3
APPROVED_SPEAKERS = frozenset({"磯貝", "阿部"})
CONTRAST_NAMES = frozenset({"plain", "minus"})
GENERATED_SOURCE_FILES = frozenset({"package-lock.json"})

FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})([^\n]*)$")
SPEAKER_RE = re.compile(r"^([一-龯々ぁ-んァ-ヶー]{1,6})「.*」\s*$")
SENTENCE_END_RE = re.compile(r"(?:[。！？]+|[!?]+(?=[」』）)]|\s|$))")

DISALLOWED_STACK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("Capacitor", r"\bCapacitor\b|@capacitor/"),
        ("NestJS", r"\bNestJS\b|@nestjs/"),
        ("Redis", r"\bRedis\b|\bioredis\b"),
        ("BullMQ", r"\bBullMQ\b|\bbullmq\b"),
        ("MinIO", r"\bMinIO\b|\bminio\b"),
        ("TanStack Router", r"TanStack\s+Router|@tanstack/(?:react-)?router"),
        ("Prisma", r"\bPrisma\b|@prisma/"),
        ("bcrypt", r"\bbcrypt(?:js)?\b"),
        ("Xcode", r"\bXcode\b"),
        ("Android Studio", r"\bAndroid\s+Studio\b"),
    )
)

STACK_ADOPTION_RE = re.compile(
    r"(?:使(?:う|います|って)|採用(?:する|します)|導入(?:する|します)|"
    r"インストール(?:する|します)|依存(?:に|へ)?追加(?:する|します))"
)

DISTRIBUTION_CONTRADICTIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "教材本文の正本を PDF 以外としている",
        re.compile(
            r"教材本文(?:の)?正本(?:は|を)\s*(?:EPUB|ZIP|webpub|Web\s*サイト)", re.I
        ),
    ),
    (
        "不採用の配布形式を採用している",
        re.compile(
            r"(?:ZIP|webpub|Web\s*サイト).{0,24}(?:で配布します|を配ります|を採用します|を使います)",
            re.I,
        ),
    ),
    (
        "EPUB を読者向け配布物として確定している",
        re.compile(
            r"EPUB.{0,24}(?:を読者に配ります|を教材本文として配ります|が正本です)", re.I
        ),
    ),
)


@dataclass(frozen=True)
class Finding:
    check: str
    path: Path
    line: int
    message: str

    def render(self) -> str:
        return f"FAIL [{self.check}] {self.path}:{self.line}: {self.message}"


@dataclass(frozen=True)
class FenceBlock:
    start_line: int
    info: str
    lines: tuple[tuple[int, str], ...]
    closed: bool


def mask_html_comments(text: str) -> str:
    """HTML コメントを改行位置を保ったまま不可視にする。"""
    return re.sub(
        r"<!--[\s\S]*?(?:-->|\Z)",
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        text,
    )


def strip_blockquote_prefix(line: str) -> str:
    value = line
    while True:
        matched = re.match(r"^[ \t]{0,3}>[ \t]?", value)
        if not matched:
            return value
        value = value[matched.end() :]


def prose_paragraphs(text: str, fenced_lines: set[int]) -> list[tuple[int, str]]:
    """可視の地の文を段落単位にし、元の開始行番号を保つ。"""
    paragraphs: list[tuple[int, str]] = []
    start_line = 0
    body: list[str] = []

    def finish() -> None:
        nonlocal start_line, body
        if body:
            paragraphs.append((start_line, " ".join(body)))
        start_line = 0
        body = []

    for line_no, original in enumerate(mask_html_comments(text).splitlines(), 1):
        if line_no in fenced_lines:
            finish()
            continue
        stripped = strip_blockquote_prefix(original).strip()
        if not stripped:
            finish()
            continue
        list_match = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)(.*)$", stripped)
        if list_match:
            finish()
            item = list_match.group(1).strip()
            if item:
                paragraphs.append((line_no, item))
            continue
        if re.match(r"^(?:#{1,6}\s|\||---+$)", stripped):
            finish()
            continue
        if not body:
            start_line = line_no
        body.append(stripped)
    finish()
    return paragraphs


def is_safe_relative_posix_path(value: object) -> TypeGuard[str]:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return False
    if value.startswith("/") or value.endswith("/") or "//" in value:
        return False
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and str(path) == value


def parse_fences(text: str) -> tuple[list[FenceBlock], set[int]]:
    """CommonMark の基本的な fenced code block とその行番号を返す。"""
    blocks: list[FenceBlock] = []
    fenced_lines: set[int] = set()
    marker_char = ""
    marker_len = 0
    start_line = 0
    info = ""
    body: list[tuple[int, str]] = []

    for line_no, original_line in enumerate(text.splitlines(), 1):
        line = strip_blockquote_prefix(original_line)
        if not marker_char:
            matched = FENCE_OPEN_RE.match(line)
            if matched:
                marker = matched.group(1)
                marker_char = marker[0]
                marker_len = len(marker)
                start_line = line_no
                info = matched.group(2).strip()
                body = []
                fenced_lines.add(line_no)
            continue

        fenced_lines.add(line_no)
        if re.match(
            rf"^[ \t]{{0,3}}{re.escape(marker_char)}{{{marker_len},}}[ \t]*$", line
        ):
            blocks.append(FenceBlock(start_line, info, tuple(body), True))
            marker_char = ""
            marker_len = 0
            start_line = 0
            info = ""
            body = []
        else:
            body.append((line_no, line))

    if marker_char:
        blocks.append(FenceBlock(start_line, info, tuple(body), False))
    return blocks, fenced_lines


def structural_findings(path: Path, text: str) -> list[Finding]:
    blocks, fenced_lines = parse_fences(text)
    findings: list[Finding] = []
    for block in blocks:
        if not block.closed:
            findings.append(
                Finding(
                    "structure/unclosed-fence",
                    path,
                    block.start_line,
                    "コードフェンスが閉じていない",
                )
            )
        if len(block.lines) > MAX_CODE_LINES:
            findings.append(
                Finding(
                    "structure/code-lines",
                    path,
                    block.start_line,
                    f"コードブロックが {len(block.lines)} 行（上限 {MAX_CODE_LINES} 行）",
                )
            )

    for line_no, paragraph in prose_paragraphs(text, fenced_lines):
        sentence_count = len(SENTENCE_END_RE.findall(paragraph))
        if sentence_count > MAX_PARAGRAPH_SENTENCES:
            findings.append(
                Finding(
                    "structure/paragraph-sentences",
                    path,
                    line_no,
                    f"段落が {sentence_count} 文（上限 {MAX_PARAGRAPH_SENTENCES} 文）",
                )
            )
    return findings


def policy_findings(path: Path, text: str) -> list[Finding]:
    blocks, fenced_lines = parse_fences(text)
    findings: list[Finding] = []

    # 技術スタックは利用を示すコードと採用表現だけを見る。歴史説明の単純な語の出現は許す。
    for block in blocks:
        code = "\n".join(line for _, line in block.lines)
        for name, pattern in DISALLOWED_STACK_PATTERNS:
            match = pattern.search(code)
            if match:
                line = next(
                    (
                        line_no
                        for line_no, value in block.lines
                        if pattern.search(value)
                    ),
                    block.start_line,
                )
                findings.append(
                    Finding(
                        "policy/disallowed-stack",
                        path,
                        line,
                        f"コードで不採用スタック {name} を使用",
                    )
                )

    for line_no, paragraph in prose_paragraphs(text, fenced_lines):
        speaker_match = SPEAKER_RE.match(paragraph)
        if speaker_match:
            speaker = speaker_match.group(1).strip()
            if speaker not in APPROVED_SPEAKERS:
                findings.append(
                    Finding(
                        "policy/speaker",
                        path,
                        line_no,
                        f"未承認の話者ラベル「{speaker}」",
                    )
                )
        for name, pattern in DISALLOWED_STACK_PATTERNS:
            match = pattern.search(paragraph)
            if not match:
                continue
            tail = paragraph[match.end() : match.end() + 36]
            if STACK_ADOPTION_RE.search(tail):
                findings.append(
                    Finding(
                        "policy/disallowed-stack",
                        path,
                        line_no,
                        f"不採用スタック {name} の採用を指示",
                    )
                )
        for message, pattern in DISTRIBUTION_CONTRADICTIONS:
            if pattern.search(paragraph):
                findings.append(Finding("policy/distribution", path, line_no, message))
    return findings


def is_contrast(path: Path) -> bool:
    stem = path.stem
    if stem in CONTRAST_NAMES and path.parent.parent.name == "g6":
        return True
    return stem.startswith("chapter-") and any(
        stem.endswith(f"-{name}") for name in CONTRAST_NAMES
    )


def infer_chapter_id(path: Path) -> str:
    if path.stem in CONTRAST_NAMES:
        return path.parent.name
    stem = path.stem
    for suffix in ("-plain", "-minus"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    if stem.startswith("chapter-"):
        stem = stem[len("chapter-") :]
    return stem


def load_start_state_manifest(path: Path) -> dict[str, dict[str, object]]:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"重複キー {key!r}")
            result[key] = value
        return result

    def reject_nonstandard_constant(value: str) -> None:
        raise ValueError(f"非標準の JSON 定数 {value!r}")

    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonstandard_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"開始状態 manifest を読めない: {error}") from error
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data["version"] != 1
        or not isinstance(data.get("chapters"), dict)
    ):
        raise ValueError(
            "開始状態 manifest は version=1 と chapters オブジェクトを持つ必要がある"
        )
    if data.get("scope") != "chapter-content-mixing-only":
        raise ValueError(
            "開始状態 manifest の scope は chapter-content-mixing-only に固定する"
        )
    if data.get("snapshot_conformance_checked") is not False:
        raise ValueError(
            "snapshot_conformance_checked は false 固定（この検査の保証範囲外）"
        )
    if set(data) != {"version", "scope", "snapshot_conformance_checked", "chapters"}:
        raise ValueError("開始状態 manifest のトップレベルに未定義キーがある")
    if not data["chapters"]:
        raise ValueError("開始状態 manifest の chapters が0件")
    for chapter_id, entry in data["chapters"].items():
        if (
            not isinstance(chapter_id, str)
            or not chapter_id
            or not isinstance(entry, dict)
        ):
            raise ValueError(
                "chapters は空でない章IDをキーとするオブジェクトで指定する"
            )
        if (
            not 3 <= len(chapter_id) <= 32
            or re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", chapter_id) is None
        ):
            raise ValueError(f"章ID {chapter_id!r} が規約外")
        required_entry_keys = {
            "snapshot",
            "allowed_state_contract",
            "forbidden_paths",
            "forbidden_patterns",
        }
        missing_entry_keys = required_entry_keys - set(entry)
        extra_entry_keys = set(entry) - required_entry_keys
        if missing_entry_keys:
            raise ValueError(
                f"章ID {chapter_id} の必要キーが無い: {', '.join(sorted(missing_entry_keys))}"
            )
        if extra_entry_keys:
            raise ValueError(
                f"章ID {chapter_id} に未定義キーがある: {', '.join(sorted(extra_entry_keys))}"
            )
        snapshot = entry.get("snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError(f"章ID {chapter_id} の snapshot が無い")
        required_snapshot_keys = {"revision", "source_root", "status", "tracked_files"}
        optional_snapshot_keys = {"allow_empty"}
        missing_snapshot_keys = required_snapshot_keys - set(snapshot)
        extra_snapshot_keys = (
            set(snapshot) - required_snapshot_keys - optional_snapshot_keys
        )
        if missing_snapshot_keys:
            raise ValueError(
                f"章ID {chapter_id} の snapshot 必要キーが無い: "
                f"{', '.join(sorted(missing_snapshot_keys))}"
            )
        if extra_snapshot_keys:
            raise ValueError(
                f"章ID {chapter_id} の snapshot に未定義キーがある: "
                f"{', '.join(sorted(extra_snapshot_keys))}"
            )
        if (
            not isinstance(snapshot.get("revision"), str)
            or not snapshot["revision"].strip()
        ):
            raise ValueError(f"章ID {chapter_id} の snapshot.revision が空")
        source_root = snapshot.get("source_root")
        if not is_safe_relative_posix_path(source_root):
            raise ValueError(f"章ID {chapter_id} の snapshot.source_root が不正")
        status = snapshot.get("status")
        if status not in {"declared-empty-trial", "unfrozen-reference-candidate"}:
            raise ValueError(f"章ID {chapter_id} の snapshot.status が不正")
        tracked_files = snapshot.get("tracked_files")
        if not isinstance(tracked_files, list):
            raise ValueError(
                f"章ID {chapter_id} の snapshot.tracked_files は配列で指定する"
            )
        if not tracked_files and snapshot.get("allow_empty") is not True:
            raise ValueError(
                f"章ID {chapter_id} の tracked_files が0件。空開始なら allow_empty=true を明示する"
            )
        if status == "declared-empty-trial" and (
            tracked_files or snapshot.get("allow_empty") is not True
        ):
            raise ValueError(f"章ID {chapter_id} の空開始宣言と tracked_files が矛盾")
        if status == "unfrozen-reference-candidate" and not tracked_files:
            raise ValueError(f"章ID {chapter_id} の参照候補に tracked file が無い")
        seen_paths: set[str] = set()
        for tracked_file in tracked_files:
            if not isinstance(tracked_file, dict):
                raise ValueError(
                    f"章ID {chapter_id} の tracked_files 要素がオブジェクトでない"
                )
            if set(tracked_file) != {"path", "sha256"}:
                raise ValueError(
                    f"章ID {chapter_id} の tracked_files 要素にキーの過不足がある"
                )
            tracked_path = tracked_file.get("path")
            digest = tracked_file.get("sha256")
            if not is_safe_relative_posix_path(tracked_path):
                raise ValueError(f"章ID {chapter_id} の tracked file path が不正")
            if tracked_path in seen_paths:
                raise ValueError(
                    f"章ID {chapter_id} の tracked file path が重複: {tracked_path}"
                )
            seen_paths.add(tracked_path)
            if (
                not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                raise ValueError(
                    f"章ID {chapter_id} の {tracked_path} に有効な sha256 が無い"
                )
        contract = entry.get("allowed_state_contract")
        if not isinstance(contract, str) or not contract.strip():
            raise ValueError(f"章ID {chapter_id} の allowed_state_contract が空")
        forbidden_paths = entry.get("forbidden_paths")
        forbidden_patterns = entry.get("forbidden_patterns")
        if not isinstance(forbidden_paths, list) or not all(
            is_safe_relative_posix_path(item) for item in forbidden_paths
        ):
            raise ValueError(f"章ID {chapter_id} の forbidden_paths が不正")
        if not isinstance(forbidden_patterns, list) or not all(
            isinstance(item, str) and item for item in forbidden_patterns
        ):
            raise ValueError(f"章ID {chapter_id} の forbidden_patterns が不正")
        if not forbidden_paths and not forbidden_patterns:
            raise ValueError(f"章ID {chapter_id} の禁止対象が0件")
        if len(forbidden_paths) != len(set(forbidden_paths)) or len(
            forbidden_patterns
        ) != len(set(forbidden_patterns)):
            raise ValueError(f"章ID {chapter_id} の禁止対象が重複")
        for source in forbidden_patterns:
            try:
                re.compile(source)
            except re.error as error:
                raise ValueError(
                    f"章ID {chapter_id} の正規表現 {source!r} が不正: {error}"
                ) from error
    return data["chapters"]


def start_state_findings(
    path: Path,
    chapter_id: str,
    chapters: dict[str, dict[str, object]],
    manifest_base: Path,
) -> list[Finding]:
    entry = chapters.get(chapter_id)
    if not isinstance(entry, dict):
        return [
            Finding(
                "start-state/definition",
                path,
                1,
                f"章ID {chapter_id} の定義が manifest に無い",
            )
        ]

    forbidden_paths = entry.get("forbidden_paths")
    forbidden_patterns = entry.get("forbidden_patterns")
    if not isinstance(forbidden_paths, list) or not all(
        isinstance(item, str) and item for item in forbidden_paths
    ):
        return [
            Finding(
                "start-state/definition",
                path,
                1,
                "forbidden_paths は空文字を含まない配列で指定する",
            )
        ]
    if not isinstance(forbidden_patterns, list) or not all(
        isinstance(item, str) and item for item in forbidden_patterns
    ):
        return [
            Finding(
                "start-state/definition",
                path,
                1,
                "forbidden_patterns は空文字を含まない配列で指定する",
            )
        ]
    if not forbidden_paths and not forbidden_patterns:
        return [
            Finding(
                "start-state/definition",
                path,
                1,
                "禁止対象が0件のため開始状態を判定できない",
            )
        ]

    snapshot = entry.get("snapshot")
    if not isinstance(snapshot, dict):
        return [Finding("start-state/definition", path, 1, "snapshot 定義が無い")]
    source_root_value = snapshot.get("source_root")
    tracked_files = snapshot.get("tracked_files")
    if not isinstance(source_root_value, str) or not isinstance(tracked_files, list):
        return [Finding("start-state/definition", path, 1, "snapshot の入力定義が不正")]

    findings: list[Finding] = []
    tracked_paths: list[str] = []
    for tracked_file in tracked_files:
        if not isinstance(tracked_file, dict):
            continue
        tracked_path_value = tracked_file.get("path")
        if isinstance(tracked_path_value, str):
            tracked_paths.append(tracked_path_value)
    for forbidden_path in forbidden_paths:
        normalized_prefix = forbidden_path.rstrip("/")
        for tracked_path in tracked_paths:
            if tracked_path == normalized_prefix or tracked_path.startswith(
                f"{normalized_prefix}/"
            ):
                findings.append(
                    Finding(
                        "start-state/mixed-content",
                        path,
                        1,
                        f"開始ソースに禁止パス {tracked_path} が混入",
                    )
                )

    manifest_root = manifest_base.resolve()
    source_root = manifest_base / source_root_value
    if tracked_paths:
        try:
            resolved_source_root = source_root.resolve(strict=True)
        except OSError as error:
            return [
                Finding(
                    "start-state/source-input",
                    path,
                    1,
                    f"開始ソースルートを読めない: {source_root}: {error}",
                )
            ]
        if not resolved_source_root.is_relative_to(manifest_root):
            return [
                Finding(
                    "start-state/source-input",
                    path,
                    1,
                    f"開始ソースルートが manifest の範囲外: {source_root}",
                )
            ]
        source_root = resolved_source_root
    source_texts: list[tuple[str, list[str]]] = []
    for tracked_path in tracked_paths:
        source_path = source_root / tracked_path
        try:
            resolved_source_path = source_path.resolve(strict=True)
        except OSError:
            resolved_source_path = source_path
        if (
            source_path.is_symlink()
            or not resolved_source_path.is_relative_to(source_root)
            or not resolved_source_path.is_file()
        ):
            findings.append(
                Finding(
                    "start-state/source-input",
                    path,
                    1,
                    f"開始ソースを読めない: {source_path}",
                )
            )
            continue
        if tracked_path in GENERATED_SOURCE_FILES:
            continue
        try:
            source_lines = resolved_source_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            findings.append(
                Finding(
                    "start-state/source-input",
                    path,
                    1,
                    f"開始ソースをUTF-8で読めない: {source_path}: {error}",
                )
            )
            continue
        source_texts.append((tracked_path, source_lines))

    for source in forbidden_patterns:
        try:
            pattern = re.compile(source)
        except re.error as error:
            findings.append(
                Finding(
                    "start-state/definition",
                    path,
                    1,
                    f"不正な正規表現 {source!r}: {error}",
                )
            )
            continue
        for tracked_path, source_lines in source_texts:
            for line_no, line in enumerate(source_lines, 1):
                if pattern.search(line):
                    findings.append(
                        Finding(
                            "start-state/mixed-content",
                            path,
                            1,
                            f"開始ソース {tracked_path}:{line_no} が禁止パターン {source!r} に一致",
                        )
                    )
    return findings


def dev_log_findings(path: Path, chapter_id: str, dev_logs_dir: Path) -> list[Finding]:
    expected = dev_logs_dir / f"{chapter_id}.md"
    if expected.is_file():
        return []
    return [Finding("dev-log/existence", path, 1, f"開発ログが無い: {expected}")]


def check_chapter(
    path: Path,
    dev_logs_dir: Path,
    chapters: dict[str, dict[str, object]] | None,
    manifest_base: Path | None = None,
) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [Finding("input", path, 1, f"教材を読めない: {error}")]
    findings = structural_findings(path, text)
    findings.extend(policy_findings(path, text))
    if is_contrast(path):
        return findings

    chapter_id = infer_chapter_id(path)
    if chapters is None:
        findings.append(
            Finding(
                "start-state/definition",
                path,
                1,
                "開始状態 manifest が指定されていない",
            )
        )
    else:
        findings.extend(
            start_state_findings(
                path,
                chapter_id,
                chapters,
                manifest_base if manifest_base is not None else Path.cwd(),
            )
        )
    findings.extend(dev_log_findings(path, chapter_id, dev_logs_dir))
    return findings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="G3 残4検査（暫定）")
    parser.add_argument(
        "chapters", nargs="+", type=Path, help="検査する章。0件は argparse が拒否する"
    )
    parser.add_argument("--dev-logs-dir", required=True, type=Path)
    parser.add_argument("--start-state-manifest", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest: dict[str, dict[str, object]] | None = None
    manifest_error = ""
    if args.start_state_manifest is not None:
        try:
            manifest = load_start_state_manifest(args.start_state_manifest)
        except ValueError as error:
            manifest_error = str(error)

    findings: list[Finding] = []
    if manifest_error:
        findings.append(
            Finding(
                "start-state/definition", args.start_state_manifest, 1, manifest_error
            )
        )
    for chapter in args.chapters:
        findings.extend(
            check_chapter(
                chapter,
                args.dev_logs_dir,
                manifest,
                args.start_state_manifest.resolve().parent
                if args.start_state_manifest is not None
                else None,
            )
        )

    if findings:
        for finding in findings:
            print(finding.render(), file=sys.stderr)
        print(
            f"暫定 G3 残4検査 FAIL: {len(findings)} 件。正式 G3 の判定ではない",
            file=sys.stderr,
        )
        return 1

    print(f"暫定 G3 残4検査 PASS: {len(args.chapters)} 件")
    print(
        "開始ソースの混入だけを検査した。manifest のハッシュ一致とsnapshot全体の適合は別検査"
    )
    print("P1/G1 前の検知テスト結果であり、正式な G3 通過証拠ではない")
    return 0


if __name__ == "__main__":
    sys.exit(main())
