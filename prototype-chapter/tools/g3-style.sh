#!/usr/bin/env bash
# G3 の「文体チェック」だけ（10 §4 G3 / 12 が文体の正本）
#
# ★ これは G3 の全部ではない。10 §4 の G3 は次の5つからなる。
#     1. 文体チェック（textlint）        ← このスクリプトが見るのはここだけ
#     2. 構造チェック（コードブロック25行以内・段落3文以内）
#     3. 開始状態の混入検査
#     4. 方針同期チェック（配布形式・不採用スタック名・人物名）
#     5. 開発ログの存在確認
#   2〜5 は tools/g3_checks.py、全体の入口は tools/g3-full.sh に実装している。
#   この文体単独スクリプトが 0 で終わっても
#   「G3 を通過した」とは言えない。26行のコードブロックも、開発ログの無い章も、
#   本文が textlint を満たしていれば素通りする。
#
# 使い方:
#   tools/g3-style.sh              章の本文すべてを検査する
#   tools/g3-style.sh chapter.md   ファイルを指定して検査する
#
# G6 の plain/minus 対照版も文体チェックの対象にする（D17-1）。開始状態混入検査と
# 開発ログ存在だけは本物側で1回確認し、対照版には重ねない。
#
# 終了コード: 0=文体チェックのみ通過 / 非ゼロ=FAIL
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
    TARGETS+=("$f")
  done
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "FAIL: 検査対象の章が1つも無い" >&2
  exit 1
fi

echo "G3 文体チェック（5検査中1つ）: ${#TARGETS[@]} 件を検査する"
"$TEXTLINT" "${TARGETS[@]}"
echo "文体チェック PASS（単独実行は G3 通過ではない）"
