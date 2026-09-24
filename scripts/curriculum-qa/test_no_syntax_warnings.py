#!/usr/bin/env python3
r"""scripts/curriculum-qa/*.py が警告なしでコンパイルできることを確認する。

`\`` のような不正なエスケープ列は Python 3.12 以降で SyntaxWarning
（3.11 では DeprecationWarning）になる。CI が新しい Python で走ると
ログに警告が出る。検査器自身が警告を出す状態を作らないため、全ファイルを
warnings-as-error でコンパイルする。
"""

import sys
import warnings
from pathlib import Path

DIR = Path(__file__).resolve().parent


def main() -> int:
    failed = 0
    files = sorted(DIR.glob("*.py"))
    for f in files:
        with warnings.catch_warnings(record=True) as got:
            warnings.simplefilter("always")
            try:
                compile(f.read_text(encoding="utf-8"), f.name, "exec")
            except SyntaxError as e:
                failed += 1
                print(f"  ❌ {f.name}: SyntaxError: {e}")
                continue
        for w in got:
            if issubclass(w.category, (SyntaxWarning, DeprecationWarning)):
                failed += 1
                print(f"  ❌ {f.name}:{w.lineno} {w.category.__name__}: {w.message}")
    if failed:
        print(f"❌ 構文警告テスト {failed} 件")
        return 1
    print(f"✅ 構文警告なし（{len(files)} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
