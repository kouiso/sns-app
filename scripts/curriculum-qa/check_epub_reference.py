#!/usr/bin/env python3
"""「手元の物と見比べてください」と書いている照合先が、読者の手元に届くかを見る。

旧 `check_zip_reference.py`（前作の販売ZIP版）の引き継ぎ。前作30周目の最重量案件は、
本文8箇所が「このリポジトリの `src/...` と見比べて」と書いていたことだった。
`build-zip.sh` は完成アプリを入れず、買った人は照合先を持っていなかった。

本作の配布は ZIP ではなく **PDF 正本・EPUB 併産＋公開リポジトリ＋章末スナップショット**
（16 B9 / D23 / `decisions/task-app資産棚卸し.md` の「3系統」）。よって照合先の判定は
「販売ZIPに入るか」ではなく「次のどれかで読者へ届くか」に置き換わる:

  - EPUB の同梱エントリ（`--epub` で EPUB 実物を渡す）
  - 開始状態・スターターのファイル（`--starter` でディレクトリか一覧を渡す）
  - 公開リポジトリに実在するファイル（`--repo-root`。完成コードは C3 で公開）

終了コード:
  0 = 判定でき、違反なし
  1 = 違反あり（読者の手元に届かない照合先への指示）
  2 = 使い方の誤り・対象ファイルが無い・成果物が読めない
  3 = 未判定。`app/` `supabase/` `snapshots/` 配下の照合先は、完成版・スターター・
      EPUB のどれもまだ存在しない間は「届く」とも「届かない」とも言えない。
      その種の参照だけが残ったときは、PASS ではなく未判定として報告する
      （「違反なし」と「まだ判定できない」を分ける。10 §4 の exit-code 原則に倣う）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from markdown_scan import paragraph_line, paragraph_text, paragraphs
from sale_package import REPO_ROOT, epub_entries, starter_paths

NOT_JUDGED = 3

# 「手元の物と突き合わせろ」と読者に言う語。
COMPARE = re.compile(r"見比べ|見くらべ|照合|突き合わせ|突合|比較して(?:確認|見)|と比べて(?:確認|み)")
# 文中に現れる置き場。リポジトリ直下からの相対でも同じ置き場を書く
# （`./app/index.tsx`、`/app/index.tsx`、`sns-app/app/index.tsx`）ので前置きを剥がす。
REPO_PREFIX = r"(?:\.{1,2}/|/|sns-app/)?"
# 置き場として扱うのは「スラッシュを持つパス」と、決まりきった直下ファイル名だけ。
# 拡張子だけで拾うと `Next.js` のような地の文の語まで照合先になる。
LOCATION = re.compile(
    rf"(?<![\w/.-]){REPO_PREFIX}"
    r"([\w.\[\]-]+/[\w./\[\]-]*[\w.\[\]-]|package\.json|app\.json|App\.tsx|tsconfig\.json)"
)
# 断りの及ぶ範囲を決めるために拾う語。末尾の階層が無い `app/` `supabase/` も取る。
DISCLAIM_SCOPE = re.compile(
    rf"(?<![\w/.-]){REPO_PREFIX}"
    r"([\w.\[\]-]+/[\w./\[\]-]*)"
)
# 「配布物には入っていません」と断ってある文は、読者を存在しない物へ送らない。
# 前作の修正はこの断りを添える形で入ったので、断りごと赤くしては直した意味が消える。
DISCLAIMED = re.compile(
    r"(?:ZIP|EPUB|PDF|配布物|本書|教材|スナップショット)\s*(?:に|には|の中に)?"
    r"[^。]{0,40}(?:入って?い?ません|入りません|含まれ(?:て?い?)?ません|同梱されません)"
)
SENTENCE_END = "。"
# 照合を指示する文が、自分で照合先を名指ししているかを見るための語。
INLINE_CODE = re.compile(r"`+([^`]+)`+")
URL = re.compile(r"https?://\S+")
NAMED_FILE = re.compile(r"[\w.\[\]-]+\.[A-Za-z0-9]{1,6}\b")
NAMED_PATH = re.compile(r"[\w.\[\]-]+/[\w./\[\]-]*")
# 照合を打ち消す語。「`app/x.tsx` と見比べる必要はありません」は正しい案内である。
NEGATED = re.compile(
    r"\n?(?:する|し|せ|る|す|て|た)?[はをも]?\n?"
    r"(?:必要(?:は)?(?:あり|ござい)?ませ[んぬ]|必要(?:は)?な(?:い|く)|不要"
    r"|ないで|なくて|ずに|ません)"
)

# この3つ配下の照合先は、完成版アプリ・スナップショット・スターターの実在に依存する。
# どれもまだ作られていない現状では「届かない」と断言できず、未判定に逃がす。
UNJUDGEABLE_PREFIXES = ("app/", "supabase/", "snapshots/")


def reachable(location: str, *, starter: frozenset[str], epub: frozenset[str], repo_root: Path) -> bool:
    """その置き場が、開始状態・EPUB・公開リポジトリのどれかで読者に届くなら True。"""
    return (
        location in starter
        or location in epub
        or (repo_root / location).is_file()
    )


def unjudgeable(location: str, *, repo_root: Path) -> bool:
    """その置き場の是非が、今存在しない成果物に依存するなら True。

    `app/` `supabase/` `snapshots/` の参照は、完成版が書かれて初めて
    「届く/届かない」が決まる。完成版がまだリポジトリに無い間に
    「手元に無い」と断言すると、正しい記述まで赤くなる。
    """
    if not location.startswith(UNJUDGEABLE_PREFIXES):
        return False
    top = location.split("/", 1)[0]
    return not (repo_root / top).is_dir()


def _demands_compare(joined: str) -> bool:
    """その文が照合を指示しているなら True。打ち消しで続く言い回しは数えない。"""
    return any(not NEGATED.match(joined, m.end()) for m in COMPARE.finditer(joined))


def _names_target(sentence: str) -> bool:
    """その文が照合先を自分で名指ししているなら True。"""
    without_url = URL.sub(" ", sentence)
    if NAMED_PATH.search(without_url):
        return True
    return any(NAMED_FILE.search(m.group(1)) for m in INLINE_CODE.finditer(without_url))


def _sentences(joined: str) -> list[tuple[int, str]]:
    """段落を句点で切る。(段落内の開始位置, 文) を返す。"""
    out: list[tuple[int, str]] = []
    start = 0
    while True:
        i = joined.find(SENTENCE_END, start)
        if i < 0:
            break
        out.append((start, joined[start : i + 1]))
        start = i + 1
    if joined[start:]:
        out.append((start, joined[start:]))
    return out


def disclaimed_locations(joined: str) -> set[str]:
    """断りが効いている置き場を返す。

    断りは、それを書いた文が名指ししている置き場にだけ効かせる。段落まるごとを
    免除にすると、断った置き場の隣に並んだ別の置き場まで一緒に免除される。
    末尾が `/` の語はその配下すべてを指す断りとして扱う。
    """
    out: set[str] = set()
    for _, sentence in _sentences(joined):
        if not DISCLAIMED.search(sentence):
            continue
        out.update(m.group(1) for m in DISCLAIM_SCOPE.finditer(sentence))
    return out


def _is_disclaimed(location: str, disclaimed: set[str]) -> bool:
    return any(
        location == d or (d.endswith("/") and location.startswith(d)) for d in disclaimed
    )


def find_refs(
    paths: list[Path],
    *,
    starter: frozenset[str] = frozenset(),
    epub: frozenset[str] = frozenset(),
    repo_root: Path = REPO_ROOT,
) -> tuple[list[tuple[str, int, str, str]], list[tuple[str, int, str]]]:
    """(違反の一覧, 未判定の一覧) を返す。

    違反は (ファイル名, 行番号, 置き場, 該当行)。未判定は (ファイル名, 行番号, 置き場)。

    照合の指示は、それを書いた文が名指ししている置き場にだけ結び付ける。
    照合を指示する文が照合先を名指ししていないときだけ、段落全体を照合先の範囲にする
    （「…と同じです。手元のコードと見比べてください。」は照合先が前の文に在る）。
    断りの範囲は段落全体のままにする。
    """
    hits: list[tuple[str, int, str, str]] = []
    pending: list[tuple[str, int, str]] = []
    for path in paths:
        for para in paragraphs(path.read_text(encoding="utf-8")):
            joined = paragraph_text(para)
            disclaimed = disclaimed_locations(joined)
            seen: set[str] = set()
            for start, sentence in _sentences(joined):
                if not _demands_compare(sentence):
                    continue
                scope, base = (sentence, start) if _names_target(sentence) else (joined, 0)
                for m in LOCATION.finditer(scope):
                    loc = m.group(1)
                    if loc in seen or _is_disclaimed(loc, disclaimed):
                        continue
                    seen.add(loc)
                    lineno, line = paragraph_line(para, base + m.start())
                    if reachable(loc, starter=starter, epub=epub, repo_root=repo_root):
                        continue
                    if unjudgeable(loc, repo_root=repo_root):
                        pending.append((path.name, lineno, loc))
                    else:
                        hits.append((path.name, lineno, loc, line.strip()))
    return hits, pending


def collect(argv_args: list[str]) -> list[Path] | int:
    targets: list[Path] = []
    for a in argv_args:
        p = Path(a)
        if p.is_dir():
            targets.extend(sorted(f for f in p.glob("*.md") if f.name != "README.md"))
        elif p.is_file():
            targets.append(p)
        else:
            print(f"❌ 見つかりません: {a}", file=sys.stderr)
            return 2
    if not targets:
        # 引数は有効だが走査対象が0件。検査を1件もしていないので
        # 緑にしない（D1 §8-3）。
        print("⏸️ 未判定: 走査対象が0件です")
        return NOT_JUDGED
    return targets


def main(argv: list[str]) -> int:
    args: list[str] = []
    starter: frozenset[str] = frozenset()
    epub: frozenset[str] = frozenset()
    repo_root = REPO_ROOT
    it = iter(argv[1:])
    for a in it:
        if a == "--starter":
            p = Path(next(it, ""))
            try:
                starter = starter_paths(p)
            except (ValueError, OSError) as e:
                print(f"❌ {e}", file=sys.stderr)
                return 2
        elif a == "--epub":
            p = Path(next(it, ""))
            try:
                epub = epub_entries(p)
            except (ValueError, OSError) as e:
                print(f"❌ {e}", file=sys.stderr)
                return 2
        elif a == "--repo-root":
            repo_root = Path(next(it, ""))
        else:
            args.append(a)
    # 既定の対象は教材本文（curriculum/ の章）だけ。prototype-chapter/ は
    # 使い捨てフィクスチャ（10 L140-143）なので既定には入れない。
    # README は目次、dev-log と道具検証の記録は本文ではないので対象にしない。
    if not args:
        targets = sorted(
            p for p in (REPO_ROOT / "curriculum").glob("*.md") if p.name != "README.md"
        )
        if not targets:
            print("⏸️ 未判定: 走査対象が0件です（教材本文がまだ無い）")
            return NOT_JUDGED
    else:
        targets = collect(args)
        if isinstance(targets, int):
            return targets

    findings, pending = find_refs(
        targets, starter=starter, epub=epub, repo_root=repo_root
    )
    if findings:
        print(f"❌ 読者の手元に届かないものとの照合を指示している {len(findings)} 件")
        for name, lineno, loc, line in findings:
            print(f"  {name}:{lineno} [{loc}] {line[:70]}")
        print("  配布物（EPUB・開始状態・公開リポジトリ）に無い旨を添えてください。")
        return 1
    if pending:
        print(f"⏸️ 未判定: 完成版・開始状態・EPUB がまだ無いため照合先の到達可否を判定できない {len(pending)} 件")
        for name, lineno, loc in pending:
            print(f"  {name}:{lineno} [{loc}]")
        print("  完成版 app/ supabase/ または配布物ができた時点で判定します。")
        return NOT_JUDGED

    print(f"✅ 照合先 OK（{len(targets)} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
