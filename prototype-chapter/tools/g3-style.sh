#!/usr/bin/env bash
# G3 の「文体チェック」だけ（10 §4 G3 / 12 が文体の正本）
#
# ★ これは G3 の全部ではない。10 §4 の G3 は5つの検査からなり、
#   このスクリプトが見るのは文体（textlint）だけ。残りの4検査
#   （構造・開始状態・方針同期・開発ログ）は tools/g3-*.sh が担う。
#   ここが 0 で終わっても「G3 を通過した」とは言えない。
#
# 使い方:
#   tools/g3-style.sh              教材本文（curriculum/*.md）すべてを検査する
#   tools/g3-style.sh chapter.md   ファイルを指定して検査する
#
# 既定の対象は教材本文だけ。prototype-chapter/ の章は教材本文ではない
# 使い捨てフィクスチャ（10 L140-143）なので既定では走査しない。フィクスチャを
# 見るときはファイルを明示して渡す（CI の参考ステップがそうしている）。
# 対照版（*-plain.md）はフィクスチャでは文体ゲートの対象外だったが、それは
# 「わざと手順書調に書いた比較材料だから」というフィクスチャ固有の理由。
# curriculum/ に置かれた章は plain でも文体を課す（D17-1）。
#
# 終了コード: 0=文体チェックのみ通過 / 1=textlint FAIL または環境不足 /
#             3=未判定（対象0件。D1 §8-3「0件は黙って緑にしない」）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
TEXTLINT="$ROOT/node_modules/.bin/textlint"

if [[ ! -x "$TEXTLINT" ]]; then
  echo "FAIL: textlint が無い。$ROOT で npm install を先に実行すること" >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  # 呼び出し側の cwd からの相対指定は、後段の cd に備えて絶対パスへ直す。
  # このまま渡すと cd 後に別の場所を探しにいく（g5-quote.sh と同じ罠）。
  TARGETS=()
  for a in "$@"; do
    if [[ "$a" = /* ]]; then TARGETS+=("$a"); else TARGETS+=("$PWD/$a"); fi
  done
else
  TARGETS=()
  for f in "$REPO"/curriculum/*.md; do
    [[ -e "$f" ]] || continue
    [[ "$f" == */README.md ]] && continue
    TARGETS+=("$f")
  done
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "⏸️ 未判定: 検査対象の章が1つも無い" >&2
  exit 3
fi

echo "G3 文体チェック（5検査中1つ）: ${#TARGETS[@]} 件を検査する"
# textlint は起動した cwd の .textlintrc を拾う。ルートの .textlintrc.json は
# 依存パッケージの無い休眠中の設定（B41）なので、リポジトリ直下から起動すると
# "No rules found" で何も検査せずに終わる。依存が実際に入っている
# prototype-chapter/ を cwd にして起動する。
cd "$ROOT"
"$TEXTLINT" "${TARGETS[@]}"
echo "文体チェック PASS（G3 はこのほか構造・開始状態・方針同期・開発ログの検査がある）"
