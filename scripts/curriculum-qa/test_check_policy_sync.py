#!/usr/bin/env python3
"""check_policy_sync.py の退行テスト。

止めるもの（不採用スタック名・旧配布語彙・規定外の話者）と、止めては
いけないもの（現行の PDF/EPUB、配布と関係ない Webサイト、磯貝・阿部の
話者ラベル）の両方を置く。片方だけでは全部を止める検査でも全部を通す
検査でも緑になってしまう。
"""

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_policy_sync  # noqa: E402

CLEAN = """# 章

阿部「この画面はどうやって出すんですか」

磯貝「Expo が表示します。端末で見えます」

本は PDF と EPUB で配ります。
"""

CASES = [
    ("素直な本文は通す", CLEAN, 0),
    ("不採用スタック名 Prisma は止める", CLEAN + "\nORM には Prisma を使います。\n", 1),
    ("小文字の prisma も止める", CLEAN + "\n```bash\nnpm i prisma\n```\n", 1),
    ("不採用スタック名 NestJS は止める", CLEAN + "\nNestJS でAPIを作ります。\n", 1),
    ("ZIP 配布の記述は止める", CLEAN + "\n教材は ZIP で配布します。\n", 1),
    ("webpub の記述は止める", CLEAN + "\nwebpub でも読めます。\n", 1),
    ("配布文脈の Webサイト は止める", CLEAN + "\nWebサイト で配布します。\n", 1),
    ("配布と無関係の Webサイト は通す", CLEAN + "\nWebサイト を見て確認します。\n", 0),
    ("規定外の話者ラベルは止める", CLEAN + "\n田中「これは何ですか」\n", 1),
    ("話者ラベルの括弧形も見る", CLEAN + "\n佐藤）質問があります。\n", 1),
    ("磯貝・阿部は通す", CLEAN + "\n磯貝）次へ進みます。\n阿部）はい。\n", 0),
    ("PDF と EPUB の記述は通す", CLEAN + "\nPDF が正本で EPUB も出ます。\n", 0),
]


def run_main(args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return check_policy_sync.main(["check_policy_sync.py", *args])


def main() -> int:
    failed = 0
    total = 0

    def expect(name, want, got):
        nonlocal failed, total
        total += 1
        if got != want:
            failed += 1
            print(f"  ❌ {name}: 終了コード {want} を期待、実際 {got}")

    for name, body, want in CASES:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "chapter-x.md"
            f.write_text(body, encoding="utf-8")
            expect(name, want, run_main([str(f)]))

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "chapter-x.md"
        f.write_text(CLEAN, encoding="utf-8")
        expect("検査語ファイルが無ければ 2", 2,
               run_main(["--terms", str(Path(d) / "absent.json"), str(f)]))

    if failed:
        print(f"❌ check_policy_sync 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_policy_sync 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
