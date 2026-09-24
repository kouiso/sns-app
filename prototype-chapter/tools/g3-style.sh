#!/usr/bin/env bash
# G3 の「文体チェック」だけ（10 §4 G3 / 12 が文体の正本）
#
# ★ これは G3 の全部ではない。10 §4 の G3 は5つの検査からなり、
#   このスクリプトが見るのは文体（textlint）だけ。残りの4検査
#   （構造・開始状態・方針同期・開発ログ）は tools/g3-*.sh が担う。
#   ここが 0 で終わっても「G3 を通過した」とは言えない。
#
# 使い方:
#   tools/g3-style.sh              捨て試作の章本文すべてを検査する
#   tools/g3-style.sh chapter.md   ファイルを指定して検査する
#
# 対象から外すもの:
#   chapter-*-plain.md … G6 の比較評価に使う対照版。わざと手順書調に書いてあるので
#                        文体ゲートに掛けても意味がない（掛けると必ず落ちる）
#
# 終了コード: 0=文体チェックのみ通過 / 1=textlint FAIL または環境不足 /
#             3=未判定（対象0件。D1 §8-3「0件は黙って緑にしない」）
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
  echo "⏸️ 未判定: 検査対象の章が1つも無い" >&2
  exit 3
fi

echo "G3 文体チェック（5検証中1つ）: ${#TARGETS[@]} 件を検査する"
"$TEXTLINT" "${TARGETS[@]}"
echo "文体チェック PASS（G3 はこのほか構造・開始状態・方針同期・開発ログの検査がある）"
