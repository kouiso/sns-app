#!/usr/bin/env python3
"""check_anchor.py の退行テスト。

素通ししてはいけないもの（指示語だけの値）と、止めてはいけないもの（実ファイル名、
実ファイルを持たない旨を書いたもの、コードブロックの外にある同じ文字列）の両方を置く。
片方だけでは、全部を止める検査でも全部を通す検査でも緑になってしまう。

実ファイル名の判定は現行構成（`app/` `supabase/`）で行う。前作の `src/` 配下は
現在のリポジトリに対応する実体が無いため、実ファイル名としても実在確認の対象としても
扱われないことを、回帰ケースで固定する。
"""

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_anchor import (  # noqa: E402
    find,
    find_missing,
    find_sample_with_real_path,
)
from check_anchor import main as check_main  # noqa: E402

# Before/After の節にあるコードは写経の対象ではない。実ファイル名を名乗らせない。
SAMPLE_CASES: list[tuple[str, str, list[tuple[int, str]]]] = [
    (
        "読み比べ用の節で実ファイル名を名乗ったら拾う",
        "#### Before（改善前のコード）\n\n```tsx\n// filepath: app/index.tsx\n```",
        [(4, "app/index.tsx")],
    ),
    (
        "読み比べ用と書いてあれば通す",
        "#### After（プロが書くコード）\n\n```tsx\n// filepath: 読み比べ用サンプル（実ファイルには対応しません）\n```",
        [],
    ),
    (
        "写経の節なら実ファイル名でよい",
        "### Step 1: 書く\n\n```tsx\n// filepath: app/index.tsx\n```",
        [],
    ),
    (
        "読み比べ用の節を抜けたら対象外に戻る",
        "#### Before（改善前のコード）\n\n### Step 2: 書く\n\n```tsx\n// filepath: app/index.tsx\n```",
        [],
    ),
    (
        "Bash の # filepath 行は見出しではないので節から抜けない",
        "#### Before（改善前のコード）\n\n```bash\n# filepath: app/tool.sh\nls\n```",
        [(4, "app/tool.sh")],
    ),
    (
        "supabase/ 配下の値も実ファイル名として拾う",
        "#### Before（改善前のコード）\n\n```tsx\n// filepath: supabase/migrations/001_init.sql\n```",
        [(4, "supabase/migrations/001_init.sql")],
    ),
    (
        "前作構成の src/ は実ファイル名として数えない",
        "#### Before（改善前のコード）\n\n```tsx\n// filepath: src/app/page.tsx\n```",
        [],
    ),
    (
        "4連で開いたブロックは3連では閉じない",
        (
            "#### Before（改善前のコード）\n\n"
            "````md\n```\nx\n```\n// filepath: app/index.tsx\n````\n"
        ),
        [(7, "app/index.tsx")],
    ),
]

CASES: list[tuple[str, str, list[tuple[int, str]]]] = [
    (
        "指示語だけの値は拾う",
        "```tsx\n// filepath: 続き\nconst a = 1;\n```",
        [(2, "続き")],
    ),
    (
        "実ファイル名なら通す",
        "```tsx\n// filepath: app/index.tsx\nconst a = 1;\n```",
        [],
    ),
    (
        "実ファイル名に続きと添えても通す",
        "```tsx\n// filepath: app/index.tsx（同じファイルの続き）\nconst a = 1;\n```",
        [],
    ),
    (
        "実ファイルを持たない旨を書けば通す",
        "```tsx\n// filepath: 読み比べ用サンプル（続き・実ファイルには対応しません）\nconst a = 1;\n```",
        [],
    ),
    (
        "同上も拾う",
        "```tsx\n// filepath: 同上\nconst a = 1;\n```",
        [(2, "同上")],
    ),
    (
        "コードブロックの外は対象外",
        "// filepath: 続き と書いた行の話をしています。\n",
        [],
    ),
    (
        "シャープで書くブロックも拾う",
        "```bash\n# filepath: 続き\nls\n```",
        [(2, "続き")],
    ),
    (
        "複数ブロックをまとめて拾う",
        "```tsx\n// filepath: 続き\n```\n\n```tsx\n// filepath: app/a.tsx\n```\n\n```tsx\n// filepath: 同上\n```",
        [(2, "続き"), (10, "同上")],
    ),
    (
        "同じ注記が2回ぶら下がったら拾う",
        "```tsx\n// filepath: app/a.tsx（同じファイルの続き）（同じファイルの続き）\n```",
        [(2, "app/a.tsx（同じファイルの続き）（同じファイルの続き）")],
    ),
    (
        "違う注記が2つ並ぶのは通す",
        "```tsx\n// filepath: app/a.tsx（Step 3 で作成）（同じファイルの続き）\n```",
        [],
    ),
    (
        "filepath の無いブロックは対象外",
        "```tsx\nconst a = 1;\n```",
        [],
    ),
]


def check_missing() -> int:
    """実在確認は呼び出し側が渡す完成版ルートに対して行う。

    ライブのリポジトリを引くと、完成版がまだ無い現状では何も判定できない。
    フィクスチャの完成版を tempdir に立てて判定する。
    """
    failed = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "app" / "(auth)").mkdir(parents=True)
        (root / "app" / "index.tsx").write_text("x", encoding="utf-8")
        (root / "app" / "(auth)" / "login.tsx").write_text("x", encoding="utf-8")
        cases: list[tuple[str, str, list[tuple[int, str]]]] = [
            (
                "完成版に無いパスは拾う",
                "```tsx\n// filepath: app/graduation/page.tsx\n```",
                [(2, "app/graduation/page.tsx")],
            ),
            (
                "完成版に在るパスは通す",
                "```tsx\n// filepath: app/index.tsx\n```",
                [],
            ),
            (
                "在るパスに注記が付いていても通す",
                "```tsx\n// filepath: app/index.tsx（同じファイルの続き）\n```",
                [],
            ),
            (
                "ルートグループの括弧はパスの一部として実在確認する",
                "```tsx\n// filepath: app/(auth)/login.tsx\n```",
                [],
            ),
            (
                "読み比べ用の断りは対象外",
                "```tsx\n// filepath: 読み比べ用サンプル（実ファイルには対応しません）\n```",
                [],
            ),
            (
                "前作構成の src/ は実在確認の対象ではない",
                "```tsx\n// filepath: src/app/page.tsx\n```",
                [],
            ),
        ]
        for name, text, expected in cases:
            got = find_missing(text, root)
            if got != expected:
                failed += 1
                print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    return failed, len(cases)


def check_exit_code() -> tuple[int, int]:
    def run(args: list[str]) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return check_main(args)

    failed = 0
    with tempfile.TemporaryDirectory() as d:
        # 完成版フィクスチャ。app/index.tsx だけが在る。
        comp = Path(d, "completed")
        (comp / "app").mkdir(parents=True)
        (comp / "app" / "index.tsx").write_text("x", encoding="utf-8")
        target = Path(d, "chapters")
        target.mkdir()
        Path(target, "ch1.md").write_text(
            "```tsx\n// filepath: app/index.tsx\n```\n", encoding="utf-8"
        )
        Path(target, "ch2.md").write_text(
            "```tsx\n// filepath: app/missing.tsx\n```\n", encoding="utf-8"
        )
        if run(["check_anchor.py", str(target / "ch1.md"), "--completed-root", str(comp)]) != 0:
            failed += 1
            print("  ❌ 完成版に在るパスだけの章で 0 を返さない")
        if run(["check_anchor.py", str(target / "ch2.md"), "--completed-root", str(comp)]) != 1:
            failed += 1
            print("  ❌ 完成版に無いパスを指す章で 1 を返さない")
        # 完成版ルートが存在しても app/ supabase/ が無ければ実在確認は未判定。
        empty = Path(d, "empty")
        empty.mkdir()
        if run(["check_anchor.py", str(target / "ch1.md"), "--completed-root", str(empty)]) != 3:
            failed += 1
            print("  ❌ 空の完成版ルート指定で 3（未判定）を返さない")
    if run(["check_anchor.py", "/no/such/path"]) != 2:
        failed += 1
        print("  ❌ 見つからないパスで 2 を返さない")
    if run(["check_anchor.py", "--completed-root", "/no/such/path", "/tmp"]) != 2:
        failed += 1
        print("  ❌ 存在しない完成版ルートで 2 を返さない")
    return failed, 5


def main() -> int:
    failed = 0
    for name, text, expected in CASES:
        got = find(text)
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    for name, text, expected in SAMPLE_CASES:
        got = find_sample_with_real_path(text)
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    missing_failed, missing_total = check_missing()
    failed += missing_failed
    exit_failed, exit_total = check_exit_code()
    failed += exit_failed
    total = len(CASES) + len(SAMPLE_CASES) + missing_total + exit_total
    if failed:
        print(f"❌ check_anchor 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_anchor 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
