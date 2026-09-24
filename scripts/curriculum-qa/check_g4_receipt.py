#!/usr/bin/env python3
"""G4 受領証の機械検査（D15-8）。

`material/reviews/g4/<章ID>.md` に置かれる受領証が、
`material/reviews/_template_G4受領証.md` の様式を満たして記入済みかを見る。
受領証は教材本文ではなく記録なので、文体ではなく「欄が埋まっているか」と
「記録が判定と矛盾していないか」を機械で見る。

検査項目（D15-8 の番号と対応）:
  1. g4/ 直下の .md の basename が章分割表の生きている章IDに含まれること
  2. 指定された対象章に受領証が存在すること（`--target`）
  3. `<...>`・空セル・「未記入」が残っていないこと
     （ただし §7 は「R3 も FAIL のときだけ記入」なので、エスカレーションが
     要らないラウンドの §7 雛形は残っていてよい）
  4. 観点表が3行あり、3行とも PASS/FAIL のどちらかであること
  5. §3.1 の3問すべてに回答があり、2・3問目が「有り」なら技術正確性が FAIL
  6. 同一対象タグのラウンドが3を超えないこと、R3 が FAIL なら §7 が埋まっていること
  7. 総合判定 PASS の受領証で、3観点のいずれかが FAIL になっていないこと

加えて:
  8. 各ラウンドの「使ったAIファミリー」と「生成側ファミリー」が別であること
     （16 A6 / D15-6。同一ファミリーでの自己レビュー禁止）
  9. ラウンド一覧の行と `# R<n>` 節が一対一で対応すること（D15-4。
     カウンタは一覧の行数で数えるので、一覧に載っていないラウンド節は
     回数の外へ抜ける抜け道になる）

終了コード:
  0 = 判定でき、違反なし
  1 = 違反あり（未知の章ID・必須受領証の欠落・未記入欄・記録の矛盾）
  2 = 使い方の誤り（章分割表が読めない・明示した --g4-dir が無い）
  3 = 未判定（g4/ が無い・空で走査対象が0件。D1 §8-3「0件は黙って
      緑にしない」）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from chapter_table import read_chapter_table
from markdown_scan import fence_states

REPO_ROOT = Path(__file__).resolve().parents[2]
G4_DIR = REPO_ROOT / "material" / "reviews" / "g4"
TABLE = REPO_ROOT / "material" / "18-chapter-split-table.md"
NOT_JUDGED = 3

# 合否を数える観点はこの3つだけ（10:208-209 / D15-3）。退屈だった箇所は
# §5 で聞いて記録するが、PASS/FAIL を付けず合否に数えない。
VIEWPOINTS = ("技術正確性", "完成品へのつながり", "文体逸脱")

# §3.1 の回答の定型（D15-8-5）。2問目・3問目が「有り」なら技術正確性は FAIL。

PLACEHOLDER = re.compile(r"<([^<>\n]{1,80})>")
# テンプレートの埋め草紙のうち日本語を含まないもの。`<sha>` `<n>` `<n+1>`
# `<YYYY-MM-DD>` は ASCII だけなので個別に挙げる。日本語を含む埋め草紙は
# CJK を含む `<...>` として別経路で拾う。
# なお `<...>` の走査はインラインコードをマスクしない。テンプレートが
# `` `<sha>` `` のようにバッククォートの中へ埋め草紙を書く以上、
# コード片の中の `<...>` も残存埋め草紙として拾うのが D15-8-3 の文字どおりの読み。
ASCII_PLACEHOLDERS = {"sha", "n", "n+1", "yyyy-mm-dd", "#n"}
CJK = re.compile(r"[ぁ-んァ-ヶ一-龯]")

ROUND_HEAD = re.compile(r"^#\s*R(\d+)\b")
ROUND_CELL = re.compile(r"^R(\d+)$")
# 対象タグは `chapter/<章ID>` または改訂タグ `chapter/<章ID>-r<K>`（10:318-322）。
TAG_CELL = re.compile(r"^`?chapter/([a-z][a-z0-9]*(?:-[a-z0-9]+)*?)(?:-r(\d+))?`?$")
# ファミリー名の揺れを吸収する見出し語。見出し語がどちらにも無いときは
# 記入文字列どうしの一致だけで判定する（未知のファミリー名を勝手に同一視しない）。
FAMILY_HINTS = {
    "claude": "claude",
    "codex": "codex",
    "gpt": "codex",
    "openai": "codex",
    "gemini": "gemini",
    "google": "gemini",
}


def prose_lines(text: str) -> list[tuple[int, str]]:
    """フェンスの外にある行を (行番号, 行) で返す。行番号は1始まり。

    受領証は根拠欄にレビュアの原文（コード断片を含みうる）を貼る。
    フェンスの中の表もどきまで欄として数えると、貼られたコードの `|` が
    空セル違反に見える。
    """
    return [(i, line) for i, line, state, _ in fence_states(text) if state != "inside"]


def table_rows(lines: list[tuple[int, str]], start: int, stop: int) -> list[tuple[int, list[str]]]:
    """[start, stop) の範囲にある表の行を (行番号, セル列) で返す。

    `|` で囲まれた行だけを取り、区切り行（`-` だけのセル）は落とす。
    """
    rows: list[tuple[int, list[str]]] = []
    for i, line in lines:
        if not (start <= i < stop):
            continue
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [c.strip() for c in line[1:-1].split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        rows.append((i, cells))
    return rows


def field_value(rows: list[tuple[int, list[str]]], name: str) -> str | None:
    """`| 項目 | 値 |` の2列表から name の値を取る。"""
    for _, cells in rows:
        if len(cells) >= 2 and cells[0] == name:
            return cells[1]
    return None


def _is_placeholder(inner: str) -> bool:
    """`<...>` の中身がテンプレートの埋め草紙か。

    埋め草紙は3種ある: 日本語を含む（`<章ID>` 等）、選択肢を ` / ` で並べる
    （`<PASS / FAIL>` 等）、`...` を含む。ASCII だけの埋め草紙は少数なので
    個別に挙げる。
    """
    s = inner.strip()
    if CJK.search(s) or " / " in s or "..." in s:
        return True
    low = s.lower()
    if low in ASCII_PLACEHOLDERS:
        return True
    return bool(re.fullmatch(r"(?:pass|fail|g\d)", low))


def _filled_rows(lines: list[tuple[int, str]], skip: tuple[int, int] | None = None) -> list[tuple[int, str]]:
    """D15-8-3: `<...>`・空セル・「未記入」の残存を (行番号, 指摘) で返す。

    skip に渡した行範囲（エスカレーション不要ラウンドの §7）は読み飛ばす。
    """
    problems: list[tuple[int, str]] = []
    for i, line in lines:
        if skip is not None and skip[0] <= i < skip[1]:
            continue
        if "未記入" in line:
            problems.append((i, "「未記入」が残っています"))
        for m in PLACEHOLDER.finditer(line):
            if _is_placeholder(m.group(1)):
                problems.append((i, f"プレースホルダ <{m.group(1)}> が残っています"))
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line[1:-1].split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells) and any(c == "" for c in cells):
                problems.append((i, "空の表セルが残っています"))
    return problems


def _section_bounds(lines: list[tuple[int, str]], prefix: str) -> tuple[int, int] | None:
    """`## <prefix>` / `### <prefix>` で始まる節の行範囲 [start, stop)。

    節の終わりは次の `## ` `### ` `# ` のどれか（受領証の節はこの3段だけ）。
    """
    start = None
    stop = None
    for i, line in lines:
        if start is None and re.match(rf"^#{{1,3}}\s+{re.escape(prefix)}", line):
            start = i
            continue
        if start is not None and i > start and re.match(r"^#{1,3}\s+", line):
            stop = i
            break
    if start is None:
        return None
    return start, stop if stop is not None else 1 << 30


def check_viewpoints(lines: list[tuple[int, str]]) -> tuple[list[tuple[int, str]], dict[str, str]]:
    """D15-8-4: 観点表が3行で、各判定が PASS/FAIL。"""
    problems: list[tuple[int, str]] = []
    verdicts: dict[str, str] = {}
    bounds = _section_bounds(lines, "3.")
    if bounds is None:
        return [(0, "## 3. 観点別 PASS/FAIL の節がありません")], verdicts
    data = [
        (i, cells) for i, cells in table_rows(lines, *bounds)
        if len(cells) >= 2 and cells[0] != "観点"
    ]
    if len(data) != len(VIEWPOINTS):
        problems.append((bounds[0], f"観点表が {len(data)} 行です（{len(VIEWPOINTS)}行必要）"))
    for i, cells in data:
        viewpoint, verdict = cells[0], cells[1]
        if viewpoint not in VIEWPOINTS:
            problems.append((
                i, f"合否を数える観点表に規定外の観点「{viewpoint}」があります"
                f"（数えるのは {(' / '.join(VIEWPOINTS))} の3つだけ）"
            ))
            continue
        if verdict not in {"PASS", "FAIL"}:
            problems.append((
                i, f"観点「{viewpoint}」の判定が PASS/FAIL ではありません: {verdict or '（空）'}"
            ))
        verdicts[viewpoint] = verdict
    for v in VIEWPOINTS:
        if v not in verdicts:
            problems.append((bounds[0], f"観点「{v}」の行がありません"))
    return problems, verdicts


def check_s31(lines: list[tuple[int, str]], verdicts: dict[str, str]) -> list[tuple[int, str]]:
    """D15-8-5: §3.1 の3問への明示回答と、有りなら技術正確性 FAIL の整合。"""
    bounds = _section_bounds(lines, "3.1")
    if bounds is None:
        return [(0, "### 3.1 引用範囲の過不足の節がありません")]
    problems: list[tuple[int, str]] = []
    data = [
        (i, cells) for i, cells in table_rows(lines, *bounds)
        if len(cells) >= 2 and cells[0] != "設問"
    ]
    if len(data) < 3:
        problems.append((bounds[0], f"§3.1 の設問が {len(data)} 行です（3行必要）"))
    answers: list[str] = []
    allowed = [("到達できる", "到達できない"), ("無し", "有り"), ("無し", "有り")]
    for pos, (i, cells) in enumerate(data[:3]):
        answer = cells[1]
        if not any(answer.startswith(a) for a in allowed[pos]):
            problems.append((i, f"§3.1 の回答が定型ではありません: {answer or '（空）'}"))
        answers.append(answer)
    if len(answers) >= 3 and any(a.startswith("有り") for a in answers[1:3]) \
            and verdicts.get("技術正確性") == "PASS":
        problems.append((
            bounds[0], "§3.1 の2・3問目に「有り」があるのに技術正確性が PASS です"
        ))
    return problems


def check_family(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """16 A6 / D15-6: レビュアと生成側が別ファミリーであること。"""
    bounds = _section_bounds(lines, "1.")
    if bounds is None:
        return [(0, "## 1. 実施条件の節がありません")]
    rows = table_rows(lines, *bounds)
    used = field_value(rows, "使ったAIファミリー")
    made = field_value(rows, "生成側ファミリー")
    if used is None or made is None:
        return [(bounds[0], "実施条件にファミリー欄がありません")]

    def family_of(value: str) -> str:
        low = value.strip("`").lower()
        for hint, family in FAMILY_HINTS.items():
            if hint in low:
                return family
        return low

    if family_of(used) == family_of(made):
        return [(
            bounds[0],
            f"レビュアと生成側が同一ファミリーです（{used} / {made}。16 A6 の自己レビュー禁止に反します）"
        )]
    return []


def check_verdict(lines: list[tuple[int, str]], verdicts: dict[str, str]) -> tuple[list[tuple[int, str]], str | None]:
    """D15-8-7: 総合判定 PASS なら3観点すべて PASS。"""
    bounds = _section_bounds(lines, "6.")
    if bounds is None:
        return [(0, "## 6. 総合判定の節がありません")], None
    verdict = field_value(table_rows(lines, *bounds), "総合判定")
    problems: list[tuple[int, str]] = []
    if verdict is None:
        problems.append((bounds[0], "総合判定の欄がありません"))
    elif verdict.startswith("PASS") and not all(verdicts.get(v) == "PASS" for v in VIEWPOINTS):
        problems.append((
            bounds[0], "FAIL 観点があるのに総合判定が PASS です（D15-8-7）"
        ))
    return problems, verdict


def check_escalation(lines: list[tuple[int, str]], need: bool) -> list[tuple[int, str]]:
    """D15-8-6: R3 が FAIL のラウンドは §7 が埋まっていること。

    `局長の裁定` は裁定が出るまで「未回答」が許される記入値なので、
    ここでは節の存在と各欄に実値があることだけを見る。埋め草紙の一般走査は
    エスカレーションが要るラウンドでは _filled_rows 側も同じ節を拾う。
    """
    bounds = _section_bounds(lines, "7.")
    if bounds is None:
        return [(0, "## 7. 局長エスカレーションの節がありません（R3 FAIL）")] if need else []
    if not need:
        return []
    rows = table_rows(lines, *bounds)
    problems: list[tuple[int, str]] = []
    for field in ("エスカレーション日", "残っている FAIL 観点", "渡した資料", "局長の裁定"):
        value = field_value(rows, field)
        if value is None:
            problems.append((bounds[0], f"§7 に「{field}」欄がありません（D15-8-6）"))
        elif value == "" or (PLACEHOLDER.fullmatch(value) and _is_placeholder(value[1:-1])):
            problems.append((bounds[0], f"§7 の「{field}」が未記入です（D15-8-6）"))
    return problems


def check_receipt(path: Path) -> list[tuple[int, str]]:
    """受領証1枚の検査。(行番号, 指摘) を返す。章IDの生死は見ない。"""
    name = path.name
    text = path.read_text(encoding="utf-8")
    lines = prose_lines(text)
    problems: list[tuple[int, str]] = []

    # 台帳のラウンド一覧で対象タグごとの回数を数える（D15-4: カウンタは
    # 一覧の行数。同一タグで R3 まで）。一覧に無いラウンド節は回数の外へ
    # 抜ける抜け道なので、節と行の一対一対応もここで見る。
    ledger: dict[tuple[str, int], int] = {}
    lb = _section_bounds(lines, "ラウンド一覧")
    if lb is None:
        problems.append((0, "台帳のラウンド一覧がありません"))
    else:
        for i, cells in table_rows(lines, *lb):
            if len(cells) < 7 or cells[0] == "ラウンド":
                continue
            rm, tm = ROUND_CELL.match(cells[0]), TAG_CELL.match(cells[1])
            if not rm or not tm:
                problems.append((i, "ラウンド一覧の行が様式と合いません"))
                continue
            ledger[(cells[1].strip("`"), int(rm.group(1)))] = i
        by_tag: dict[str, list[int]] = {}
        for tag, n in ledger:
            by_tag.setdefault(tag, []).append(n)
        for tag, rounds in by_tag.items():
            if len(rounds) > 3:
                problems.append((0, f"対象タグ {tag} のラウンドが {len(rounds)} 回（同一タグは R3 まで。D15-4）"))
            if sorted(rounds) != list(range(1, len(rounds) + 1)):
                problems.append((0, f"対象タグ {tag} のラウンド番号が連番ではありません: {sorted(rounds)}"))

    # 各ラウンドの節。# R<n> で切る。最初の # R より前（題名と台帳）も
    # 未記入の対象なので先に走査する。
    heads = [(i, int(m.group(1))) for i, line in lines for m in [ROUND_HEAD.match(line)] if m]
    preamble_end = heads[0][0] if heads else 1 << 30
    problems.extend(_filled_rows([(i, l) for i, l in lines if i < preamble_end]))
    seen_ledger: set[tuple[str, int]] = set()
    for idx, (start_i, round_no) in enumerate(heads):
        stop_i = heads[idx + 1][0] if idx + 1 < len(heads) else 1 << 30
        section = [(i, l) for i, l in lines if start_i <= i < stop_i]
        label = f"R{round_no}"

        vp_problems, verdicts = check_viewpoints(section)
        problems.extend(vp_problems)
        problems.extend(check_s31(section, verdicts))
        problems.extend(check_family(section))
        v_problems, verdict = check_verdict(section, verdicts)
        problems.extend(v_problems)

        if _section_bounds(section, "5.") is None:
            problems.append((start_i, f"{label} に ## 5. 退屈だった箇所 の節がありません（記録欄は必須。D15-3）"))

        # このラウンドの対象タグを §1 から引き、一覧の行と対応させる。
        tag_key = ""
        b1 = _section_bounds(section, "1.")
        if b1 is not None:
            tag_value = field_value(table_rows(section, *b1), "対象タグ") or ""
            tag_key = tag_value.strip("`")
        if tag_key and (tag_key, round_no) in ledger:
            seen_ledger.add((tag_key, round_no))
            is_r3 = round_no == 3
        elif tag_key:
            problems.append((start_i, f"{label} の対象タグ {tag_key} はラウンド一覧に行がありません（D15-4 のカウンタ外）"))
            is_r3 = round_no == 3
        else:
            is_r3 = round_no == 3

        need_escalation = is_r3 and verdict == "FAIL"
        s7 = _section_bounds(section, "7.")
        problems.extend(check_escalation(section, need_escalation))

        # エスカレーション不要のラウンドでは §7 は雛形のまま残るのが正しい姿
        # （「R3 も FAIL のときだけ記入」）ので、その節の埋め草紙・空セルは
        # 未記入違反に数えない。
        skip = s7 if not need_escalation else None
        problems.extend(_filled_rows(section, skip))

    # 一覧にあって節の無い行も止める（逆方向のずれ）。
    for (tag, n), i in ledger.items():
        if (tag, n) not in seen_ledger:
            problems.append((i, f"ラウンド一覧の R{n}（{tag}）に対応する # R{n} 節がありません"))

    if not heads:
        problems.append((0, "ラウンド節（# R1 など）がありません"))
    return problems


def check_g4_dir(g4_dir: Path, live_ids: set[str], target: str | None = None) -> list[tuple[str, int, str]]:
    """g4/ ディレクトリ全体の検査。(ファイル名, 行番号, 指摘) を返す。

    live_ids は章分割表の生きている章IDの集合（呼び出し側が渡す）。
    target に章IDを渡すと、その受領証の存在を要求する（D15-8-2）。
    """
    problems: list[tuple[str, int, str]] = []
    receipts = sorted(g4_dir.glob("*.md"))
    for path in receipts:
        if path.name == "README.md":
            continue
        chapter_id = path.stem
        if chapter_id not in live_ids:
            problems.append((path.name, 0, f"章ID `{chapter_id}` は章分割表の現役章にありません（D15-8-1）"))
            continue
        for line, msg in check_receipt(path):
            problems.append((path.name, line, msg))
    if target is not None and not (g4_dir / f"{target}.md").is_file():
        problems.append((f"{target}.md", 0, f"章 `{target}` の G4 受領証がありません（G4 未実施。D15-8-2）"))
    return problems


def main(argv: list[str]) -> int:
    g4_dir = G4_DIR
    g4_dir_given = False
    table = TABLE
    targets: list[str] = []
    it = iter(argv[1:])
    for a in it:
        if a == "--g4-dir":
            g4_dir = Path(next(it, ""))
            g4_dir_given = True
        elif a == "--table":
            table = Path(next(it, ""))
        elif a == "--target":
            targets.append(next(it, ""))
        else:
            print(f"❌ 不明な引数: {a}", file=sys.stderr)
            return 2

    try:
        result = read_chapter_table(table, REPO_ROOT)
    except (OSError, UnicodeError, ValueError) as e:
        print(f"❌ 章分割表が読めません: {e}", file=sys.stderr)
        return 2
    live_ids = {row["章ID"] for row in result["chapters"]}
    if not live_ids:
        print("❌ 章分割表から生きている章IDが取れません", file=sys.stderr)
        return 2

    if not g4_dir.is_dir():
        # 既定の置き場が無いのは「受領証がまだ作られていない」＝未判定。
        # 明示された --g4-dir が無いのは使い方の誤り。
        if g4_dir_given:
            print(f"❌ 受領証の置き場がありません: {g4_dir}", file=sys.stderr)
            return 2
        print("⏸️ 未判定: 受領証の置き場がまだありません（material/reviews/g4/）")
        return NOT_JUDGED

    problems: list[tuple[str, int, str]] = []
    receipts = sorted(p for p in g4_dir.glob("*.md") if p.name != "README.md")
    if not receipts and not targets:
        # 走査対象が0件。D1 §8-3「0件は黙って緑にしない」。
        print("⏸️ 未判定: 受領証がまだありません（material/reviews/g4/）")
        return NOT_JUDGED
    for path in receipts:
        chapter_id = path.stem
        if chapter_id not in live_ids:
            problems.append((path.name, 0, f"章ID `{chapter_id}` は章分割表の現役章にありません（D15-8-1）"))
            continue
        for line, msg in check_receipt(path):
            problems.append((path.name, line, msg))
    for target in targets:
        if not (g4_dir / f"{target}.md").is_file():
            problems.append((f"{target}.md", 0, f"章 `{target}` の G4 受領証がありません（G4 未実施。D15-8-2）"))

    if problems:
        print(f"❌ G4 受領証の検査で {len(problems)} 件の問題")
        for name, line, msg in problems:
            where = f"{name}:{line}" if line else name
            print(f"  {where} {msg}")
        return 1
    print(f"✅ G4 受領証 OK（{len(receipts)} 件）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
