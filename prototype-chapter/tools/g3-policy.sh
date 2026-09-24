#!/usr/bin/env bash
# G3 の「方針同期チェック」（13 §5 / 10 §4 G3）。
# 配布形式の旧語彙・不採用スタック名・登場人物名の矛盾を教材本文から検出する。
# 対照版 *-plain.md も対象（D17-1 で方針同期は対照版にも課される）。
#
# 使い方:
#   tools/g3-policy.sh             curriculum/ と prototype-chapter の章本文を検査
#   tools/g3-policy.sh file.md …   ファイルを指定して検査
#
# 終了コード: 0=PASS / 1=違反あり / 2=対象・データファイルが読めない
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
CHECK="$REPO/scripts/curriculum-qa/check_policy_sync.py"

if [[ $# -gt 0 ]]; then
  TARGETS=("$@")
else
  TARGETS=()
  for f in "$REPO"/curriculum/*.md "$ROOT"/chapter*.md; do
    # README.md は目次・ナビ文書であり章本文ではないので対象外
    [[ -e "$f" && "$(basename "$f")" != "README.md" ]] && TARGETS+=("$f")
  done
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "⏸️  G3 方針同期チェック: 対象の章がまだ無い"
  exit 0
fi

python3 "$CHECK" "${TARGETS[@]}"
