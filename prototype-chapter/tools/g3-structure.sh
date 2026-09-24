#!/usr/bin/env bash
# G3 の「構造チェック」（10 §4 G3: コードブロック25行以内・段落3文以内）。
#
# 使い方:
#   tools/g3-structure.sh             curriculum/ と prototype-chapter の章本文を検査
#   tools/g3-structure.sh file.md …   ファイルを指定して検査
#
# 終了コード: 0=PASS / 1=違反あり / 2=対象が読めない
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
CHECK="$REPO/scripts/curriculum-qa/check_structure.py"

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
  # 教材本文がまだ無い。構造チェックはファイル単位の検査なので、
  # 対象0件は「通した」ではなく「まだ無い」として通す。
  echo "⏸️  G3 構造チェック: 対象の章がまだ無い"
  exit 0
fi

python3 "$CHECK" "${TARGETS[@]}"
