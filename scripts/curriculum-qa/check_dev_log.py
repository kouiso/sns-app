#!/usr/bin/env python3
r"""開発ログの存在確認（10 §5 / D1-7 / D16-7）。

章Nの実装中に `dev-logs/<章ID>.md` が「実装のその場で」書かれる。
記録がない章は対話のハマり場面を創作することになり、内容の嘘に戻るので、
存在を G3 の検査項目に含める。例外・条件つきで通す余地は無い（D16-7）。

対象章は `--chapter <章ID>` で明示する。省略時は `curriculum/*.md` の
basename（README を除く）を対象とする — curriculum/ に章があるのに
dev-logs/ が無ければ、その章はログ未作成のまま進んでいる。
prototype-chapter/ の章は対象に含めない。捨て試作は教材本文ではない
使い捨てフィクスチャで（10:104-107 / D15-10-3）、その記録は
`prototype-chapter/dev-log.md` に1本で済ませている。

様式（10 §5 のテンプレート）:
  - `# 開発ログ — 章 \`<章ID>\``
  - `### 詰まりN` の節が1つ以上
  - 各節に8項目（何をしようとした / 出たエラー（全文コピー） /
    最初に疑ったこと（間違いでもそのまま書く）/ 実際の原因 /
    解決した手順 / かかった時間 / friction種別 / 教材に載せる価値）
  - friction種別は beginner / ai-artifact / unobserved のどれか
  - 教材に載せる価値は 高 / 中 / 低 のどれか
  - 「価値: 高」の詰まりは章の対話に必ず登場させる（10 §5）。
    機械では「出たエラーの最初の1行が章本文に現れるか」で近似する。
    章本文が見つからないときは判定を保留して警告に留める。

警告（FAIL ではない）: 詰まりがすべて ai-artifact の章は対話素材が不足
している（10 §5）。

終了コード: 0 = 違反なし、1 = 違反あり、2 = 使い方の誤り、
3 = 未判定（対象の章が0件。D1 §8-3）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from markdown_scan import fence_states

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_LOGS = REPO_ROOT / "dev-logs"
NOT_JUDGED = 3
# 「価値:高」が章の対話に登場したかを見るための章本文の探し順。
# curriculum/<章ID>.md が正本。prototype-chapter/chapter-<章ID>.md も見るのは、
# 章が curriculum/ に移る前の段階でも警告だけは出せるようにするためで、
# 存在確認の対象を広げる意味ではない（対象は curriculum/ のみ。10 L140-143）。
CHAPTER_DIRS = (REPO_ROOT / "curriculum", REPO_ROOT / "prototype-chapter")

TITLE = re.compile(r"^#\s*開発ログ\s*—\s*章\s*`?([a-z][a-z0-9]*(?:-[a-z0-9]+)*)`?\s*$")
ENTRY = re.compile(r"^###\s*詰まり(\d+)\s*$")
FIELD = re.compile(r"^-\s*(\S[^:：]*)[:：]\s*(.*)$")

REQUIRED_FIELDS = (
    "何をしようとした",
    "出たエラー（全文コピー）",
    "最初に疑ったこと（間違いでもそのまま書く）",
    "実際の原因",
    "解決した手順",
    "かかった時間",
    "friction種別",
    "教材に載せる価値",
)
FRICTIONS = ("beginner", "ai-artifact", "unobserved")
VALUES = ("高", "中", "低")


def chapter_text(chapter_id: str, dirs: tuple[Path, ...] = CHAPTER_DIRS) -> str | None:
    """章IDから章本文を引く。見つからなければ None。"""
    for d in dirs:
        for cand in (d / f"{chapter_id}.md", d / f"chapter-{chapter_id}.md"):
            if cand.is_file():
                return cand.read_text(encoding="utf-8")
    return None


def check_log(path: Path, chapter_id: str, dirs: tuple[Path, ...] = CHAPTER_DIRS) -> tuple[list[str], list[str]]:
    """ログ1件の検査。(違反, 警告) を返す。"""
    problems: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    tm = next((TITLE.match(l) for l in lines if TITLE.match(l)), None)
    if tm is None:
        problems.append(f"{path.name}: 「# 開発ログ — 章 `<章ID>`」の題名がありません")
    elif tm.group(1) != chapter_id:
        problems.append(f"{path.name}: 題名の章ID `{tm.group(1)}` がファイル名と一致しません")

    entries = [(i, int(m.group(1))) for i, l in enumerate(lines) if (m := ENTRY.match(l))]
    if not entries:
        problems.append(f"{path.name}: 「### 詰まりN」の節がありません（unobserved も記録対象）")
        return problems, warnings

    frictions: list[str] = []
    for idx, (start, _n) in enumerate(entries):
        stop = entries[idx + 1][0] if idx + 1 < len(entries) else len(lines)
        section = lines[start:stop]
        label = f"{path.name}:詰まり{idx + 1}(L{start + 1})"
        # フェンスの中の `- 項目: 値` は欄ではない（貼られたエラーの一部）。
        # 「出たエラー（全文コピー）」は全文をフェンスで貼る書き方があるので、
        # 欄の直後のフェンスの中身をその値として拾う。
        fields: dict[str, str] = {}
        pending_error = False
        fence_body: list[str] = []
        for _ln, line, state, _fence in fence_states("\n".join(section)):
            if state == "outside":
                fm = FIELD.match(line)
                if fm:
                    fields[fm.group(1).strip()] = fm.group(2).strip()
                    pending_error = fm.group(1).strip() == "出たエラー（全文コピー）"
                    continue
                if line.strip():
                    pending_error = False
            elif pending_error and state in ("inside", "close"):
                if state == "inside":
                    fence_body.append(line)
                else:
                    inline = fields["出たエラー（全文コピー）"]
                    fields["出たエラー（全文コピー）"] = (
                        inline + "\n" + "\n".join(fence_body)
                    ).strip()
                    pending_error = False
        for key in REQUIRED_FIELDS:
            if key not in fields:
                problems.append(f"{label} 項目「{key}」がありません")
            elif not fields[key]:
                problems.append(f"{label} 項目「{key}」が空です")
        fr = fields.get("friction種別", "")
        if fr:
            matched = next((f for f in FRICTIONS if f in fr), None)
            if matched is None:
                problems.append(f"{label} friction種別 `{fr}` は beginner / ai-artifact / unobserved のどれでもありません")
            else:
                frictions.append(matched)
        value = fields.get("教材に載せる価値", "")
        if value and value not in VALUES:
            problems.append(f"{label} 教材に載せる価値 `{value}` は 高 / 中 / 低 のどれでもありません")
        if value == "高":
            # 「高」の詰まりは対話に必ず登場させる（10 §5）。機械の近似として
            # 出たエラーの最初の1行が章本文に現れるかを見る。
            err = fields.get("出たエラー（全文コピー）", "").splitlines()
            first = next((l.strip() for l in err if l.strip()), "")
            body = chapter_text(chapter_id, dirs)
            if body is None:
                warnings.append(f"{label} 価値「高」ですが章本文が見つからず対話への登場を確認できません")
            elif first and first not in body:
                problems.append(f"{label} 価値「高」のエラーが章本文の対話に現れていません: {first[:40]}")

    if frictions and all(f == "ai-artifact" for f in frictions):
        warnings.append(f"{path.name}: 詰まりがすべて ai-artifact です。対話素材が不足しています（10 §5）")
    return problems, warnings


def main(argv: list[str]) -> int:
    dev_logs = DEV_LOGS
    chapter_dirs = CHAPTER_DIRS
    chapters: list[str] = []
    it = iter(argv[1:])
    for a in it:
        if a == "--dev-logs":
            dev_logs = Path(next(it, ""))
            # 明示した置き場が無いのは指定ミス（2）。既定の置き場が無いのは
            # 「まだ書かれていない」で各章の違反（1）。混ぜない。
            if not dev_logs.is_dir():
                print(f"❌ 開発ログの置き場が見つかりません: {dev_logs}", file=sys.stderr)
                return 2
        elif a == "--chapters-dir":
            cd = Path(next(it, ""))
            if not cd.is_dir():
                print(f"❌ 章本文の置き場が見つかりません: {cd}", file=sys.stderr)
                return 2
            chapter_dirs = (cd,)
        elif a == "--chapter":
            chapters.append(next(it, ""))
        else:
            chapters.append(a)

    if not chapters:
        # 対象は教材本文 curriculum/<章ID>.md だけ。prototype-chapter/ は
        # 使い捨てフィクスチャ（10 L140-143）で、ここの章IDは将来の実章と
        # 衝突しうるのでログ要求の根拠にしない（D1-7）。
        curriculum = REPO_ROOT / "curriculum"
        if curriculum.is_dir():
            chapters.extend(p.stem for p in curriculum.glob("*.md") if p.stem != "README")
        chapters = sorted(set(chapters))
    if not chapters:
        print("⏸️ 未判定: 対象の章が0件です（教材本文がまだ無い）")
        return NOT_JUDGED

    problems: list[str] = []
    warnings: list[str] = []
    for chapter_id in chapters:
        path = dev_logs / f"{chapter_id}.md"
        if not path.is_file():
            problems.append(f"章 `{chapter_id}` の開発ログがありません: dev-logs/{chapter_id}.md")
            continue
        p, w = check_log(path, chapter_id, chapter_dirs)
        problems.extend(p)
        warnings.extend(w)

    for w in warnings:
        print(f"⚠️ {w}")
    if problems:
        print(f"❌ 開発ログの検査で {len(problems)} 件")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"✅ 開発ログ OK（対象 {len(chapters)} 章）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
