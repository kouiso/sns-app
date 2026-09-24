#!/usr/bin/env python3
"""check_structure.py の退行テスト。

止めるもの（中身26行のコードブロック・4文の段落・セリフの中の4文）と、
止めてはいけないもの（ちょうど25行・3文・1文の箇条書き・インラインコードや
HTML コメントの中の句点）の両方を置く。片方だけだと、全部を止める検査でも
全部を通す検査でも緑になってしまう。
"""

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_structure import (  # noqa: E402
    find_long_code_blocks,
    find_long_paragraphs,
)
from check_structure import main as check_main  # noqa: E402


def block(inner: int, *, fence: str = "```tsx", close: str = "```") -> str:
    """中身 inner 行のコードブロックを返す。"""
    return f"{fence}\n" + "\n".join(f"line{i}" for i in range(inner)) + f"\n{close}\n"


CODE_CASES: list[tuple[str, str, list[tuple[int, int]]]] = [
    (
        "中身26行のブロックを止める",
        block(26),
        [(1, 26)],
    ),
    (
        "中身ちょうど25行は通す",
        block(25),
        [],
    ),
    (
        "閉じ忘れたフェンスも中身を数える",
        # 末尾に改行を付けない。付けると最後の空行まで中身として数わる。
        "```tsx\n" + "\n".join(f"line{i}" for i in range(26)),
        [(1, 26)],
    ),
    (
        "2個目のブロックは開始フェンスの行番号を指す",
        "```\na\n```\n\n" + block(26),
        [(5, 26)],
    ),
    (
        "チルダのフェンスも数える",
        block(26, fence="~~~tsx", close="~~~"),
        [(1, 26)],
    ),
    (
        "フェンスの行は中身に数えない",
        # 中身24行＋開き閉じ2行 = 物理26行でも中身は24行。
        block(24),
        [],
    ),
]

PARA_CASES: list[tuple[str, str, list[tuple[int, int]]]] = [
    (
        "4文の段落を止める",
        "あ。い。う。え。\n",
        [(1, 4)],
    ),
    (
        "3文の段落は通す",
        "あ。い。う。\n",
        [],
    ),
    (
        "物理2行に割れた4文も止める",
        "あ。い。\nう。え。\n",
        [(1, 4)],
    ),
    (
        "語の途中の折り返しで文を割らない",
        "あいう\nえ。い。う。\n",
        [],
    ),
    (
        "セリフの句点も文として数える",
        "磯貝「a。b。c。d」\n",
        [(1, 4)],
    ),
    (
        "文末記号のない段落は1文として通す",
        "あいうえお\n",
        [],
    ),
    (
        "括弧で終わる3文は通す",
        "「あ。い。う。」\n",
        [],
    ),
    (
        "1文の箇条書きはそれぞれ自分の段落",
        "- あ。\n- い。\n- う。\n- え。\n",
        [],
    ),
    (
        "箇条書きの中の4文は止める",
        "- あ。い。う。え。\n",
        [(1, 4)],
    ),
    (
        "見出しと表の行はそれぞれ自分の段落",
        "# あ。\n\n| a | b |\n| --- | --- |\n| c | d |\n",
        [],
    ),
    (
        "インラインコードの中の句点は数えない",
        "説明。`「。」「。」「。」`終わり。\n",
        [],
    ),
    (
        "HTML コメントだけの行は段落に入れない",
        "あ。い。う。\n\n<!-- え。お。か。き。 -->\n",
        [],
    ),
    (
        "段落の中の HTML コメントも数えない",
        "あ。い。<!-- え。お。か。 -->う。\n",
        [],
    ),
    (
        "違反は段落ごとに行番号で報告する",
        "あ。い。う。え。\n\nx。y。z。w。\n",
        [(1, 4), (3, 4)],
    ),
    (
        "コードブロックの中の文は段落ではない",
        "あ。\n\n```md\nい。う。え。お。\n```\n",
        [],
    ),
    (
        # 句点の直後が `」` で同じ行に本文が続くなら、その句点は引用内の文を
        # 終えただけで段落の文は続いている。`「これは例です。」と言った。` は
        # 外側1文 + 後続の2文で計3文。
        "引用の直後に地の文が続く句点は段落の文を終えない",
        "「これは例です。」と言った。次の文。三つ目。\n",
        [],
    ),
    (
        # 同じ形でも後続の文が多ければ止める（緩めすぎない）。
        "引用＋地の文でも4文なら止める",
        "「例です。」と言った。次。三つ目。四つ目。\n",
        [(1, 4)],
    ),
    (
        # `」` が行末で閉じる句点は発話の最後の文を終えるので数える。
        "行末で閉じる発話内の句点は文末として数える",
        "磯貝「a。b。c。」\n",
        [],
    ),
    (
        # 発話が行末で閉じても、次の行は同じ段落の続きとして数える。
        "行を跨いだ段落の文末は次の行も数える",
        "磯貝「a。」\nそして言った。締めの文。\n",
        [],
    ),
    (
        # 逆に、行末で閉じる発話の句点＋後続行で上限を超えるなら止める。
        "発話3文＋後続2文は5文として止める",
        "磯貝「a。b。c。」\nそして言った。締めの文。\n",
        [(1, 5)],
    ),
    (
        # `！？` の連なりは1つの文末。`えっ！？本当に。それも。` は
        # 読者には3文に見える（記号を1個ずつ数えると4文に化ける）。
        "連続する文末記号は1つの文末として数える",
        "えっ！？本当に。それも。\n",
        [],
    ),
    (
        "感嘆符の連なりだけの文は1文",
        "えっ！？\n",
        [],
    ),
    (
        "引用内の記号の連なりも1つ。地の文が続くなら段落を終えない",
        "「え？！」と言った。次。三つ目。\n",
        [],
    ),
    (
        # 緩めた分の取りこぼしが無いことの確認。連続区間を1つに
        # 数えても4文なら止める。
        "連続記号を1つに数えても4文なら止める",
        "えっ！？本当に。それも。さらに。\n",
        [(1, 4)],
    ),
]


def check_exit_code() -> tuple[int, int]:
    def run(args: list[str]) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            return check_main(args)

    failed = 0

    def expect(name: str, args: list[str], want: int) -> None:
        nonlocal failed
        if run(args) != want:
            failed += 1
            print(f"  ❌ {name}: 期待 {want}")

    with tempfile.TemporaryDirectory() as d:
        Path(d, "day01.md").write_text(block(26), encoding="utf-8")
        expect("違反のあるディレクトリで 1 を返す", ["check_structure.py", d], 1)
        expect(
            "ファイルを直接指定しても 1 を返す",
            ["check_structure.py", str(Path(d, "day01.md"))],
            1,
        )

    with tempfile.TemporaryDirectory() as d:
        Path(d, "day01.md").write_text("あ。い。う。\n", encoding="utf-8")
        Path(d, "day02.md").write_text(block(3, fence="```", close="```"), encoding="utf-8")
        expect("違反がなければ 0 を返す", ["check_structure.py", d], 0)

    expect(
        "見つからないパスで 2 を返す",
        ["check_structure.py", "/no/such/path"],
        2,
    )

    with tempfile.TemporaryDirectory() as d:
        expect(
            "対象ファイルが無ければ 3（未判定。D1 §8-3）を返す",
            ["check_structure.py", d],
            3,
        )

    return failed, 5


def main() -> int:
    failed = 0
    for name, text, expected in CODE_CASES:
        got = find_long_code_blocks(text)
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    for name, text, expected in PARA_CASES:
        got = find_long_paragraphs(text)
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    exit_failed, exit_total = check_exit_code()
    failed += exit_failed
    total = len(CODE_CASES) + len(PARA_CASES) + exit_total
    if failed:
        print(f"❌ check_structure 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_structure 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
