#!/usr/bin/env python3
"""18_章分割表.md の共通読み取り。下書きの構造検査でありG1承認ではない。

CLIは構造有効なら0、不正なら1、読み取り不能なら2。未決が残る正しい下書きも0。
呼び出し側は declaredGateInputsComplete を正式ゲート判定に流用しないこと。
書式と責務は material/decisions/20260919-章表の下書き検査.md を参照。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import TypedDict

from markdown_scan import fence_states

CHAPTER_COLUMNS = (
    "章ID", "並び順", "パート", "章タイトル", "完成する状態", "前提とする前章成果",
    "supersedes", "状態", "節目", "地図", "見える変化", "最初の結果", "未決依存",
)
TRACE_COLUMNS = ("章ID", "FR", "画面", "SQL/RLS", "テスト", "前提知識", "証拠")
PARTS = ("A0", "A", "B", "C", "D", "E")
STATES = {"未着手", "実装済", "教材ドラフト", "完了", "tombstone"}
ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
BACKLOG_ID = re.compile(r"[BC][1-9][0-9]*")
FRS = {f"FR{i}" for i in range(1, 16)}
SCOPE = "sns-app/material/18_章分割表.md"


class ChapterTableResult(TypedDict):
    draftStructureValid: bool
    unresolvedDependencies: list[str]
    declaredGateInputsComplete: bool
    activeChapterCount: int
    coveredFRs: list[str]
    chapters: list[dict[str, str]]
    errors: list[str]
    incompleteDeclarations: list[str]


def _valid_id(value: str) -> bool:
    return bool(ID.fullmatch(value) and 3 <= len(value) <= 32
                and not value.rsplit("-", 1)[-1].isdigit())


def _items(value: str) -> list[str]:
    if value == "-":
        return []
    items = [item.strip() for item in value.split(",")]
    if not all(items) or len(set(items)) != len(items):
        raise ValueError(f"空または重複したリスト項目: {value!r}")
    return items


def _prose(text: str) -> list[str]:
    # 例の中の表やコメントを実データとして受理しない。
    if "<!--" in text or "-->" in text:
        raise ValueError("章表ではHTMLコメントを使わないでください")
    states = list(fence_states(text))
    if states and states[-1][2] in {"open", "inside"}:
        raise ValueError("閉じていないコードフェンス")
    return [line for _, line, state, _ in states if state == "outside"]


def _read_table(lines: list[str], section: str, columns: tuple[str, ...], *, optional=False) -> list[dict[str, str]]:
    headings = [i for i, line in enumerate(lines) if line == f"## {section}"]
    if not headings and optional:
        return []
    if len(headings) != 1:
        raise ValueError(f"{section}: 見出しは1つ必要です")
    start = headings[0] + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    content = [line for line in lines[start:end] if line.strip()]
    if len(content) < 3:
        raise ValueError(f"{section}: 表が空または不足しています")
    cells = []
    for line in content:
        if not line.startswith("|") or not line.endswith("|") or "\\|" in line:
            raise ValueError(f"{section}: 表専用の節です。各行を | で囲み、セル内に | を使わないでください")
        row = [cell.strip() for cell in line[1:-1].split("|")]
        if len(row) != len(columns):
            raise ValueError(f"{section}: 列数不一致 ({len(row)} != {len(columns)})")
        cells.append(row)
    if tuple(cells[0]) != columns:
        raise ValueError(f"{section}: 列名・順序が規約と一致しません")
    if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells[1]):
        raise ValueError(f"{section}: 区切り行が不正です")
    return [dict(zip(columns, row)) for row in cells[2:]]


def _local_file(value: str, root: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"証拠はリポジトリ内の相対パスで指定してください: {value}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError(f"参照ファイルが存在しないか範囲外です: {value}")
    if not resolved.stat().st_size:
        raise ValueError(f"参照ファイルが空です: {value}")
    return resolved


def _fields(lines: list[str], required: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for key in required:
        values = [line[len(key) + 2:].strip() for line in lines if line.startswith(f"{key}: ")]
        if len(values) != 1 or not values[0]:
            raise ValueError(f"{key}: 一意で空でない記録が必要です")
        result[key] = values[0]
    return result


def _exceptions(lines: list[str], active: list[dict[str, str]], revision: str, root: Path) -> set[tuple[str, ...]]:
    rows = _read_table(lines, "tool連続例外", ("対象章", "ADR", "承認記録"), optional=True)
    active_ids = {row["章ID"] for row in active}
    approved = set()
    for row in rows:
        ids = tuple(_items(row["対象章"]))
        if len(ids) < 3 or not set(ids) <= active_ids or ids in approved:
            raise ValueError("tool例外の対象が不正・廃止済み・重複です")
        expected = {"版": revision, "対象章": ",".join(ids), "ゲート": "G1",
                    "種別": "tool連続例外", "範囲": SCOPE}
        adr = _local_file(row["ADR"], root)
        approval = _local_file(row["承認記録"], root)
        if adr == approval:
            raise ValueError("ADRと承認記録を分離してください")
        for path in (adr, approval):
            fields = _fields(_prose(path.read_text(encoding="utf-8")), tuple(expected))
            if fields != expected:
                raise ValueError(f"例外の対象・版・ゲート・種別が一致しません: {path.name}")
        fields = _fields(_prose(approval.read_text(encoding="utf-8")), ("判断", "承認者", "ADR"))
        if fields != {"判断": "承認", "承認者": "局長", "ADR": row["ADR"]}:
            raise ValueError("対応する局長承認の記録がありません")
        approved.add(ids)
    return approved


def _supersedes(chapters: list[dict[str, str]]) -> None:
    """既存の章ライフサイクルを、履歴IDを失わない最小書式で照合する。"""
    by_id = {row["章ID"]: row for row in chapters}
    uses: dict[str, list[str]] = {}
    origins: dict[str, list[str]] = {}
    for row in chapters:
        value = row["supersedes"]
        if value == "-":
            continue
        operation, separator, sources = value.partition(":")
        if not separator or operation not in {"split", "merge", "rename"}:
            raise ValueError(f"{row['章ID']}: supersedesは後継章側にsplit/merge/rename対応を記録します")
        old_ids = _items(sources)
        if (operation in {"split", "rename"} and len(old_ids) != 1) or (operation == "merge" and len(old_ids) < 2):
            raise ValueError(f"{row['章ID']}: supersedesの元ID数が不正")
        for old_id in old_ids:
            if not _valid_id(old_id):
                raise ValueError(f"supersedesの元IDが不正: {old_id}")
            if operation == "rename":
                if old_id in by_id:
                    raise ValueError(f"改名前IDが再利用されています: {old_id}")
            elif old_id not in by_id or by_id[old_id]["状態"] != "tombstone":
                raise ValueError(f"supersedesの元IDは実在するtombstoneが必要: {old_id}")
            uses.setdefault(old_id, []).append(operation)
        origins[row["章ID"]] = old_ids
    for old_id, operations in uses.items():
        if operations[0] == "split":
            if len(operations) < 2 or set(operations) != {"split"}:
                raise ValueError(f"分割元 {old_id} は2章以上への分割にだけ使用できます")
        elif len(operations) != 1:
            raise ValueError(f"supersedesの元IDを重複使用しています: {old_id}")
    # 後継が後に廃止されても系譜を残す。履歴側の循環も拒否する。
    pending = dict(origins)
    while pending:
        ready = {chapter for chapter, ancestors in pending.items() if not set(ancestors) & pending.keys()}
        if not ready:
            raise ValueError("supersedesの履歴が循環しています")
        for chapter in ready:
            del pending[chapter]


def validate_chapter_table(text: str, root: Path, known_dependency_ids: set[str] | None = None) -> ChapterTableResult:
    """構造・宣言済み参照を検査する。承認者の真正性や実測内容は検証しない。"""
    result: ChapterTableResult = {
        "draftStructureValid": False,
        "unresolvedDependencies": [],
        "declaredGateInputsComplete": False,
        "activeChapterCount": 0,
        "coveredFRs": [],
        "chapters": [],
        "errors": [],
        "incompleteDeclarations": [],
    }
    try:
        lines = _prose(text)
        revision = _fields(lines, ("版",))["版"]
        designation = _fields(lines, ("位置づけ",))["位置づけ"]
        if designation != "DRAFT / NON-G1":
            raise ValueError("この検査の対象は位置づけが DRAFT / NON-G1 の下書きです")
        chapters = _read_table(lines, "章一覧", CHAPTER_COLUMNS)
        traces = _read_table(lines, "対応表", TRACE_COLUMNS)
        ids = set()
        active = []
        for row in chapters:
            chapter_id = row["章ID"]
            if not _valid_id(chapter_id) or chapter_id in ids:
                raise ValueError(f"不正・重複・再利用された章ID: {chapter_id}")
            ids.add(chapter_id)
            if row["状態"] not in STATES:
                raise ValueError(f"{chapter_id}: 不正な状態")
            if row["状態"] == "tombstone":
                continue
            for column in ("並び順", "パート", "章タイトル", "完成する状態", "地図", "最初の結果"):
                if row[column] in {"", "-"}:
                    raise ValueError(f"{chapter_id}: {column} が空")
            if not re.fullmatch(r"-?[0-9]+", row["並び順"]):
                raise ValueError(f"{chapter_id}: 並び順が整数ではありません")
            if row["パート"] not in PARTS or row["見える変化"] not in {"screen", "tool"}:
                raise ValueError(f"{chapter_id}: パートまたは見える変化が不正")
            if row["節目"] not in {"", "-", "節目", "非節目"}:
                raise ValueError(f"{chapter_id}: 節目の指定が不正")
            active.append(row)
        _supersedes(chapters)
        if {row["パート"] for row in active} != set(PARTS):
            raise ValueError("全パート A0/A/B/C/D/E に現役章が必要です")
        active.sort(key=lambda row: int(row["並び順"]))
        orders = [int(row["並び順"]) for row in active]
        if len(set(orders)) != len(orders):
            raise ValueError("現役章の並び順が重複しています")
        part_order = [PARTS.index(row["パート"]) for row in active]
        if part_order != sorted(part_order):
            raise ValueError("パートの並びが A0 → A → B → C → D → E ではありません")
        active_ids = {row["章ID"] for row in active}
        seen = set()
        unresolved = set()
        for row in active:
            for dependency in _items(row["前提とする前章成果"]):
                if dependency not in seen:
                    raise ValueError(f"{row['章ID']}: 前提 {dependency} が存在しない・廃止・後方参照・循環です")
            seen.add(row["章ID"])
            dependencies = _items(row["未決依存"])
            if not all(BACKLOG_ID.fullmatch(item) for item in dependencies):
                raise ValueError(f"{row['章ID']}: 未決IDの書式が不正")
            if known_dependency_ids is not None and not set(dependencies) <= known_dependency_ids:
                raise ValueError(f"{row['章ID']}: 台帳にない未決ID")
            unresolved.update(dependencies)
            if row["節目"] in {"", "-"}:
                result["incompleteDeclarations"].append(f"{row['章ID']}: 節目未指定")
        result["unresolvedDependencies"] = sorted(unresolved)
        approvals = _exceptions(lines, active, revision, root)
        runs = []
        run = []
        for row in active:
            if row["見える変化"] == "tool":
                run.append(row["章ID"])
            else:
                if len(run) >= 3:
                    runs.append(tuple(run))
                run = []
        if len(run) >= 3:
            runs.append(tuple(run))
        if set(runs) != approvals:
            raise ValueError("toolが3章以上連続: 対象全体に一致するADR・承認が必要（余分な例外も不可）")
        seen_traces = set()
        covered = set()
        for row in traces:
            chapter_id = row["章ID"]
            if chapter_id not in active_ids or chapter_id in seen_traces:
                raise ValueError(f"対応表: 不明・廃止・重複した現在の章参照: {chapter_id}")
            seen_traces.add(chapter_id)
            frs = set(_items(row["FR"]))
            if not frs <= FRS:
                raise ValueError(f"{chapter_id}: 不明なFR")
            covered.update(frs)
            for column in ("画面", "SQL/RLS", "テスト", "前提知識"):
                if row[column] in {"", "-"}:
                    raise ValueError(f"{chapter_id}: 対応表の {column} が空（対象外なら理由を書く）")
            evidence = _items(row["証拠"])
            if not evidence:
                result["incompleteDeclarations"].append(f"{chapter_id}: 証拠未指定")
            for path in evidence:
                _local_file(path, root)
        if seen_traces != active_ids:
            raise ValueError("対応表に現役章の漏れがあります")
        if covered != FRS:
            raise ValueError(f"対応表にFRの漏れがあります: {','.join(sorted(FRS - covered))}")
        result["draftStructureValid"] = True
        result["declaredGateInputsComplete"] = not unresolved and not result["incompleteDeclarations"]
        result["activeChapterCount"] = len(active)
        result["coveredFRs"] = sorted(covered, key=lambda item: int(item[2:]))
        result["chapters"] = active
    except (ValueError, OSError, UnicodeError) as error:
        result["errors"].append(str(error))
    return result


def read_chapter_table(path: Path, root: Path) -> ChapterTableResult:
    text = path.read_text(encoding="utf-8")
    ledger = (root / "material/16_決定バックログ.md").read_text(encoding="utf-8")
    known_ids = set(re.findall(r"^\| ([BC][1-9][0-9]*) \|", ledger, re.MULTILINE))
    if not known_ids:
        raise ValueError("未決台帳のIDを読み取れません")
    return validate_chapter_table(text, root, known_ids)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=root / "material/18_章分割表.md")
    args = parser.parse_args()
    try:
        result = read_chapter_table(args.path, root)
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"draftStructureValid": False, "unresolvedDependencies": [],
                          "declaredGateInputsComplete": False, "errors": [str(error)]}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["draftStructureValid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
