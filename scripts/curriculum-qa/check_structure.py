#!/usr/bin/env python3
"""G3 構造チェック。コードブロックの行数と段落の文数が上限を超えていないか見る。

根拠は material/10_教材制作フロー.md §4 の G3 機械ゲート: 「構造チェック
（初期値は前作実績値: コードブロック25行以内・段落3文以内。確定値は
Phase 2 のゲート実装時に検知テストと共に固定）」。長いコードブロックは
写経中に全体を見失わせ、長い段落は技術書として読みにくい。前作の実績から
来た上限なので、確定値が決まるまで初期値を緩めてはいけない。

既定の対象は教材本文（curriculum/*.md、README.md は目次なので除く）。
prototype-chapter/ は教材本文ではない使い捨てフィクスチャ（10 L140-143）
なので既定では走査しない。フィクスチャを見たいときはファイルを明示して
渡す（CI の参考ステップがそうしている）。

判定は文字どおり行う。セリフの中の句点も1文と数え、箇条書き・表・見出しは
それぞれ独立した段落として数える。

終了コード: 0=PASS（検査した）、1=FAIL（違反あり）、2=使い方の誤り、
3=未判定（走査対象が0件。D1 §8-3「0件は黙って緑にしない」）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from markdown_scan import (
    code_blocks,
    mask_inline_code,
    paragraph_text,
    paragraphs,
)

# 上限の出典は 10 §4 G3。初期値は前作実績値で、確定値は Phase 2 の
# ゲート実装時に検知テストと共に固定する。それまで緩めてはいけない。
MAX_CODE_BLOCK_LINES = 25
MAX_PARAGRAPH_SENTENCES = 3

# 文の終わりとみなす記号。半角ピリオドは `package.json` や `v1.2` のように
# 文の終わりでない場所にも現れ、機械では区別がつかないので数えない。
SENTENCE_END = "。！？!?"

# 文末記号のあとに付くだけの閉じ記号。`「あ。い。う。」` のように段落が
# 括弧で終わるとき、末尾の `」` だけを4文目と数えると、読者に3文と見える
# 段落を止めてしまう。括弧そのものは文を始めないので、判定の前に落とす。
TRAIL_CLOSERS = "」』）)］]〉》”\"'"

# 発話・引用を閉じる括弧。句点の直後にこれが来て、さらに同じ行に本文が
# 続くなら、その句点は括弧の中の文を終えたのであって段落の文を終えていない。
QUOTE_CLOSERS = "」』"

NOT_JUDGED = 3


def _counts_as_sentence_end(joined: str, i: int) -> bool:
    """joined の i 文字目の文末記号が、段落の文を終えるものかを返す。

    `「これは例です。」と言った。` の `す。」` は引用内の句点で、外側の文は
    `と言った。` まで続く。句点の直後に `」`/`』` が来て、同じ行にまだ本文が
    続く場合は文末と数えない。一方 `磯貝「A。B。C。D」` のように括弧が行末で
    閉じる場合は、内側の句点はそのまま文末になる（セリフの中の文は数える）。
    """
    j = i + 1
    while j < len(joined) and joined[j] in QUOTE_CLOSERS:
        j += 1
    if j == i + 1:
        return True
    rest = joined[j:].split("\n", 1)[0]
    return not rest.strip()


def find_long_code_blocks(text: str) -> list[tuple[int, int]]:
    """上限を超えるコードブロックを (開始フェンスの行番号, 中身の行数) で返す。

    行番号は1始まり。閉じ忘れたフェンスも code_blocks() がそこまでの中身を
    返すので、その範囲が誰にも見えないまま緑になることはない。開始フェンスは
    中身の1行前にある。
    """
    hits: list[tuple[int, int]] = []
    for _lang, body in code_blocks(text):
        if len(body) > MAX_CODE_BLOCK_LINES:
            hits.append((body[0][0] - 1, len(body)))
    return hits


def find_long_paragraphs(text: str) -> list[tuple[int, int]]:
    """上限を超える段落を (最初の行番号, 文数) で返す。行番号は1始まり。

    日本語の本文は語の途中でも折り返すので、段落は1行ずつ見ずに繋げてから
    数える。繋がないと、折り返しで割れた1文を2文と数えてしまう。繋ぐときは
    改行を残す（sep="\n"）。`。` の直後が `」`/`』` かつ同じ行に続きがあるかを
    見る判定（_counts_as_sentence_end）が行境界を必要とするため。
    インラインコードは数える前に塗りつぶす。`「。」` の中の句点まで地の文の
    文数に足されると、読者に見えている文数と判定がずれる。

    文末記号の後ろに残った文の切れ端も1文と数える。`磯貝「a。b。c。d」` の
    末尾 `d」` は記号を持たないが読者には4文目に見える。ここを数えないと
    最後の1文だけゲートを素通りする。記号が0個の段落はこの規則で1文になる。
    """
    hits: list[tuple[int, int]] = []
    for para in paragraphs(text):
        joined = mask_inline_code(paragraph_text(para, sep="\n"))
        # 連続する文末記号（`えっ！？`）は1つの文末として数える。`！？` を
        # 2文と数えると読者に1文と見える段落を止めてしまう。区間の判定に
        # 渡す位置は連続区間の最後の記号（直後の `」` と行の続きを見るため）。
        marks = 0
        i = 0
        while i < len(joined):
            if joined[i] in SENTENCE_END:
                j = i
                while j + 1 < len(joined) and joined[j + 1] in SENTENCE_END:
                    j += 1
                if _counts_as_sentence_end(joined, j):
                    marks += 1
                i = j + 1
            else:
                i += 1
        # 末尾が文末記号なら記号の数がそのまま文数。そうでなければ、
        # 最後の記号の後ろに続く文（記号が無ければ段落全体）を足す。
        tail = joined.rstrip().rstrip(TRAIL_CLOSERS).rstrip()
        sentences = marks if tail and tail[-1] in SENTENCE_END else marks + 1
        if sentences > MAX_PARAGRAPH_SENTENCES:
            hits.append((para[0][0], sentences))
    return hits


def main(argv: list[str]) -> int:
    # 引数なしの既定は教材本文（curriculum/ の章）。捨て試作は教材本文では
    # ない（10 L140-143）ので既定には入れない。cwd によらず動くよう、
    # リポジトリの根はこのファイルの位置から引く。
    # README は目次、dev-log と道具検証の記録は本文ではないので対象にしない。
    repo = Path(__file__).resolve().parents[2]
    args = argv[1:]
    targets: list[Path] = []
    if not args:
        targets.extend(sorted(f for f in (repo / "curriculum").glob("*.md") if f.name != "README.md"))
    for a in args:
        p = Path(a)
        if p.is_dir():
            # README.md は目次・ナビ文書であり章本文ではないので対象外
            targets.extend(sorted(f for f in p.glob("*.md") if f.name != "README.md"))
        elif p.is_file():
            targets.append(p)
        else:
            print(f"❌ 見つかりません: {a}", file=sys.stderr)
            return 2

    if not targets:
        print("⏸️ 未判定: 走査対象が0件です（教材本文がまだ無い）")
        return NOT_JUDGED

    findings: list[tuple[str, int, str]] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        for line, n in find_long_code_blocks(text):
            findings.append(
                (path.name, line, f"コードブロック {n} 行（上限 {MAX_CODE_BLOCK_LINES} 行）")
            )
        for line, n in find_long_paragraphs(text):
            findings.append(
                (path.name, line, f"段落 {n} 文（上限 {MAX_PARAGRAPH_SENTENCES} 文）")
            )

    if findings:
        print(f"❌ 構造チェック違反 {len(findings)} 件")
        for name, line, msg in sorted(findings):
            print(f"  {name}:{line} {msg}")
        print("  ブロックは分けるか、段落は文末で切ってください。")
        return 1

    print(f"✅ 構造チェック OK（{len(targets)} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
