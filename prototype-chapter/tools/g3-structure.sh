#!/usr/bin/env bash
# G3 の「構造チェック」（10 §4 G3: コードブロック25行以内・段落3文以内）。
#
# 使い方:
#   tools/g3-structure.sh             教材本文（curriculum/*.md）を検査
#   tools/g3-structure.sh file.md …   ファイルを指定して検査
#                                     （捨て試作を見るときは chapter*.md を明示）
#
# 終了コード: 0=PASS / 1=違反あり / 2=使い方の誤り / 3=未判定（対象0件）。
# 3 のまま返す。0 への読み替えは tools/gate-step.sh が一括で担う。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"

python3 "$REPO/scripts/curriculum-qa/check_structure.py" "$@"
