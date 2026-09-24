#!/usr/bin/env bash
# G3 の「方針同期チェック」（13 §5 / 10 §4 G3）。
# 配布形式の旧語彙・不採用スタック名・登場人物名の矛盾を教材本文から検出する。
#
# 使い方:
#   tools/g3-policy.sh             教材本文（curriculum/*.md）を検査
#   tools/g3-policy.sh file.md …   ファイルを指定して検査
#
# 終了コード: 0=PASS / 1=違反あり / 2=使い方の誤り / 3=未判定（対象0件）。
# 3 のまま返す。0 への読み替えは tools/gate-step.sh が一括で担う。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"

python3 "$REPO/scripts/curriculum-qa/check_policy_sync.py" "$@"
