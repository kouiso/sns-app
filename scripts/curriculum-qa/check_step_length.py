#!/usr/bin/env python3
"""
コードブロック長さチェックスクリプト
全てのコードブロックが25行以下であることを確認
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markdown_scan import code_blocks  # noqa: E402


def check_code_blocks(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # フェンスの走査は markdown_scan.code_blocks() に任せる。
    # 2026-08-09（codex 指摘・2回目）: 自前の正規表現は2度直しても足りなかった。
    #   1回目 … ``` しか見ておらず `~~~` を1個も認識しなかった。
    #   2回目 … 開きと閉じの本数を同数に縛ったので、3個で開いて4個で閉じる
    #           正当な形（Markdown は「開き以上」を許す）と、字下げしたフェンスを取り落とした。
    # **同じ走査を2か所で書いている限り、片方だけ直る。**共有の走査器は
    # 入れ子・チルダ・字下げ・本数違いをすでに扱っているので、そちらへ寄せる。
    code_blocks_found = [
        [line for _, line in body]
        for _lang, body in code_blocks(content)
    ]

    errors = []
    for i, lines in enumerate(code_blocks_found, 1):
        line_count = len(lines)

        if line_count > 25:
            errors.append(f"❌ コードブロック#{i}: {line_count}行（上限25行）")
            # 最初の3行と最後の3行を表示
            print(f"\nコードブロック#{i} ({line_count}行):")
            print('\n'.join(lines[:3]))
            print("...")
            print('\n'.join(lines[-3:]))

    if errors:
        print(f"\n合計{len(errors)}個のコードブロックが制限超過")
        for error in errors:
            print(error)
        sys.exit(1)

    print(f"✅ 全{len(code_blocks_found)}個のコードブロックが25行以下")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用法: python check_step_length.py <filepath>")
        sys.exit(1)

    check_code_blocks(sys.argv[1])
