#!/usr/bin/env bash
# G3 文体ゲート（10 §4 G3 / 12 が文体の正本）
#
# 使い方:
#   tools/g3-style.sh              章の本文すべてを検査する
#   tools/g3-style.sh chapter.md   ファイルを指定して検査する
#
# 対象から外すもの:
#   chapter-*-plain.md … G6 の比較評価に使う対照版。わざと手順書調に書いてあるので
#                        文体ゲートに掛けても意味がない（掛けると必ず落ちる）
#
# 終了コード: 0=PASS / 非ゼロ=FAIL
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXTLINT="$ROOT/node_modules/.bin/textlint"

if [[ ! -x "$TEXTLINT" ]]; then
  echo "FAIL: textlint が無い。$ROOT で npm install を先に実行すること" >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  TARGETS=("$@")
else
  TARGETS=()
  for f in "$ROOT"/chapter*.md; do
    [[ -e "$f" ]] || continue
    [[ "$f" == *-plain.md ]] && continue
    TARGETS+=("$f")
  done
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "FAIL: 検査対象の章が1つも無い" >&2
  exit 1
fi

echo "G3 文体ゲート: ${#TARGETS[@]} 件を検査する"
"$TEXTLINT" "${TARGETS[@]}"
echo "G3 PASS"
