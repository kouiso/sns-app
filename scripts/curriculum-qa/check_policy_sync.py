#!/usr/bin/env python3
"""方針同期チェック（13 §5 / 10 §4 G3 / D16-8）。

方針を定めた文書（00〜16）と教材本文が矛盾していないかを機械で見る。
前作は「ZIP配布しない」方針と「ZIPを展開して」という本文が5.5ヶ月
矛盾したままだった（13 §5）。検査対象語は `policy_sync_terms.json` に置き、
方針改訂と同じPRで更新する。

検査対象は教材本文（curriculum/*.md、README.md は目次なので除く。
対照版 *-plain.md が curriculum/ に置かれた場合はそれも含む — D17-1 で
対照版にも方針同期は課される）。prototype-chapter/ は教材本文ではない
使い捨てフィクスチャ（10 L140-143）なので既定では走査しない。
設計文書 material/ は検査対象ではない。方針の履歴や決定の経緯を書く場所
なので、旧語彙が残っていること自体が正当である。

検査する3系統:
  1. 不採用スタック名（Capacitor / NestJS / Redis / BullMQ / MinIO /
     TanStack Router / Prisma / bcrypt / Xcode）が本文に登場したら FAIL。
     コードブロックの中も見る — 教材のコードに不採用物が写るのは
     本文に書くより悪い。
  2. 配布形式の旧語彙（ZIP / webpub / 配布文脈の Webサイト）。現行は
     PDF 正本・EPUB 併産（16 B9 / D23）。
  3. 登場人物名の統一。話者ラベル（`名前「` / `名前）`）に正本の2名
     （磯貝・阿部）以外が現れたら FAIL（12 §1.1「話者ラベルの整合」）。

終了コード: 0 = 違反なし、1 = 違反あり、2 = 使い方の誤り、
3 = 未判定（走査対象が0件。D1 §8-3）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TERMS = Path(__file__).resolve().parent / "policy_sync_terms.json"

NOT_JUDGED = 3
DEFAULT_TARGETS = ("curriculum/*.md",)

# 「Webサイト」は配布形式として書かれたときだけ矛盾になる。同一行に配布を
# 示す語が無い出現（「Webサイトを見る」等）は教材でも起きうるので止めない。
DIST_CONTEXT = re.compile(r"配布|公開|購入|販売|ダウンロード|教材本文|提供")

# 話者ラベル。行頭の漢字・カタカナ2〜8字のあとに、`「〜」` で終わる行か
# `）` に本文が続く形を話者と見る。ひらがなを含めると `次に「保存」を押す`
# のような普通の文を話者と誤認する（「 は行末で閉じる形だけに絞る）。
# `）` は `手順）` のような節見出しと区別するため、後続の文字を要求する。
SPEAKER = re.compile(r"^([ァ-ヶ一-龯]{2,8})(?:「.*」\s*$|）.)")


def _word_re(term: str) -> re.Pattern:
    # ASCII の製品名は前後が英字の一部でないことだけ要求する。`MinIO` が
    # `minios` の一部に当たる事故は避けたいが、`prisma` の小文字表記は拾いたい
    # ので大文字小文字は区別しない。
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def main(argv: list[str]) -> int:
    terms_path = TERMS
    targets: list[Path] = []
    it = iter(argv[1:])
    for a in it:
        if a == "--terms":
            terms_path = Path(next(it, ""))
            continue
        p = Path(a)
        if p.is_dir():
            targets.extend(sorted(f for f in p.glob("*.md") if f.name != "README.md"))
        elif p.is_file():
            targets.append(p)
        else:
            print(f"❌ 見つかりません: {a}", file=sys.stderr)
            return 2

    try:
        terms = json.loads(terms_path.read_text(encoding="utf-8"))
        rejected = terms["rejected_stack"]
        obsolete_dist = terms["obsolete_distribution"]
        characters = terms["characters"]
    except (OSError, ValueError, KeyError) as e:
        print(f"❌ 検査語のデータファイルが読めません: {e}", file=sys.stderr)
        return 2

    if not targets:
        for pat in DEFAULT_TARGETS:
            targets.extend(sorted(REPO_ROOT.glob(pat)))
        # README.md は目次・ナビ文書であり章本文ではないので対象外
        targets = [t for t in targets if t.name != "README.md"]
    if not targets:
        print("⏸️ 未判定: 走査対象が0件です（教材本文がまだ無い）")
        return NOT_JUDGED

    rejected_res = [(t, _word_re(t)) for t in rejected]
    problems: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for term, rex in rejected_res:
                if rex.search(line):
                    problems.append(f"{path.name}:{i} 不採用スタック `{term}` が本文にあります")
            for term in obsolete_dist:
                if term == "Webサイト":
                    if "Webサイト" in line and DIST_CONTEXT.search(line):
                        problems.append(f"{path.name}:{i} 配布形式の旧語彙 `Webサイト` が本文にあります")
                elif re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", line, re.IGNORECASE):
                    problems.append(f"{path.name}:{i} 配布形式の旧語彙 `{term}` が本文にあります")
            m = SPEAKER.match(line)
            if m and m.group(1) not in characters:
                problems.append(f"{path.name}:{i} 話者ラベル `{m.group(1)}` は正本の登場人物（{'・'.join(characters)}）にありません")

    if problems:
        print(f"❌ 方針同期チェックで {len(problems)} 件")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"✅ 方針同期 OK（{len(targets)} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
