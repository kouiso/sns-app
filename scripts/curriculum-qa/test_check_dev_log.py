#!/usr/bin/env python3
"""check_dev_log.py の退行テスト。

止めるもの（ログの不存在・題名の不備・必須項目の欠落・空欄・範囲外の
ラベル・価値「高」が対話に現れない）と、止めてはいけないもの
（テンプレートどおりのログ、ai-artifact だけの章=警告、章本文が無い
ときの「高」=警告）の両方を置く。
"""

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_dev_log  # noqa: E402

CID = "some-chapter"

ENTRY = """### 詰まり1
- 何をしようとした: 画面を出す
- 出たエラー（全文コピー）: Unable to resolve module foo
- 最初に疑ったこと（間違いでもそのまま書く）: パスの打ち間違い
- 実際の原因: キャッシュの残り
- 解決した手順: npx expo start -c
- かかった時間: 20分
- friction種別: beginner
- 教材に載せる価値: 中
"""

VALID = f"# 開発ログ — 章 `{CID}`\n\n{ENTRY}"


def run_main(args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return check_dev_log.main(["check_dev_log.py", *args])


def check_log_only(name, body, want_problems, want_warnings):
    """check_log を直接呼んで違反・警告の有無だけを見る。"""
    problems, warnings = check_dev_log.check_log(_write_tmp(body), CID, dirs=())
    ok = bool(problems) == want_problems and bool(warnings) == want_warnings
    return ok, problems, warnings


def _write_tmp(body):
    import tempfile as _t
    f = Path(_t.mkdtemp()) / f"{CID}.md"
    f.write_text(body, encoding="utf-8")
    return f


def main() -> int:
    failed = 0
    total = 0

    def expect(name, cond, detail=""):
        nonlocal failed, total
        total += 1
        if not cond:
            failed += 1
            print(f"  ❌ {name} {detail}")

    # ログ単体の検査（章本文は見つからない前提で dirs=() を渡す）
    ok, p, w = check_log_only("正しいログは通す", VALID, False, False)
    expect("正しいログは通す", ok, f"{p} {w}")

    ok, p, w = check_log_only("題名が無ければ止める", ENTRY, True, False)
    expect("題名が無ければ止める", ok, f"{p} {w}")

    ok, p, w = check_log_only(
        "必須項目の欠落は止める",
        VALID.replace("- 実際の原因: キャッシュの残り\n", ""), True, False)
    expect("必須項目の欠落は止める", ok, f"{p} {w}")

    ok, p, w = check_log_only(
        "項目の空欄は止める",
        VALID.replace("- かかった時間: 20分", "- かかった時間:"), True, False)
    expect("項目の空欄は止める", ok, f"{p} {w}")

    ok, p, w = check_log_only(
        "範囲外の friction種別 は止める",
        VALID.replace("friction種別: beginner", "friction種別: luck"), True, False)
    expect("範囲外の friction種別 は止める", ok, f"{p} {w}")

    ok, p, w = check_log_only(
        "範囲外の価値は止める",
        VALID.replace("教材に載せる価値: 中", "教材に載せる価値: 激高"), True, False)
    expect("範囲外の価値は止める", ok, f"{p} {w}")

    ok, p, w = check_log_only(
        "ai-artifact だけの章は警告で止めない",
        VALID.replace("friction種別: beginner", "friction種別: ai-artifact"), False, True)
    expect("ai-artifact だけの章は警告で止めない", ok, f"{p} {w}")

    ok, p, w = check_log_only(
        "unobserved も記録として通す",
        VALID.replace("friction種別: beginner", "friction種別: unobserved"), False, False)
    expect("unobserved も記録として通す", ok, f"{p} {w}")

    # 「価値: 高」と対話登場の検査。章本文の有無で FAIL / 警告が分かれる。
    high = VALID.replace("教材に載せる価値: 中", "教材に載せる価値: 高")
    with tempfile.TemporaryDirectory() as d:
        chapters = Path(d)
        (chapters / f"{CID}.md").write_text(
            "磯貝「`Unable to resolve module foo` が出たときは…」\n", encoding="utf-8")
        p, w = check_dev_log.check_log(_write_tmp(high), CID, dirs=(chapters,))
        expect("価値「高」が対話に現れれば通す", not p and not w, f"{p} {w}")
        (chapters / f"{CID}.md").write_text("磯貝「順調ですね」\n", encoding="utf-8")
        p, w = check_dev_log.check_log(_write_tmp(high), CID, dirs=(chapters,))
        expect("価値「高」が対話に無ければ止める", bool(p), f"{p} {w}")
    p, w = check_dev_log.check_log(_write_tmp(high), CID, dirs=())
    expect("章本文が無い「高」は警告に留める", not p and bool(w), f"{p} {w}")

    # main() 経由: 存在確認と終了コード。
    with tempfile.TemporaryDirectory() as d:
        logs = Path(d)
        expect("対象章のログが無ければ 1", 1 == run_main(["--dev-logs", str(logs), CID]), "")
        (logs / f"{CID}.md").write_text(VALID, encoding="utf-8")
        expect("対象章のログがあれば 0", 0 == run_main(["--dev-logs", str(logs), CID]), "")
        (logs / f"{CID}.md").write_text(ENTRY, encoding="utf-8")
        expect("中身が雛形未満なら 1", 1 == run_main(["--dev-logs", str(logs), CID]), "")

    if failed:
        print(f"❌ check_dev_log 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_dev_log 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
