#!/usr/bin/env bash
# G5 引用ゲート（10 §4 G5）
#
# 教材に貼ったコードが listings/ の実ファイルとズレていないかを embedmd で照合する。
#
# 使い方:
#   tools/g5-quote.sh              章の本文すべてを照合する
#   tools/g5-quote.sh chapter.md   ファイルを指定して照合する
#
# ★ embedmd -d の終了コードは 1 ではなく 2 である（実測。道具検証の記録 §3）。
#   判定を「exit 1 なら FAIL」と書くとズレを見逃すため、非ゼロを FAIL として扱う。
#
# ★ このゲートが緑でも、引用範囲が足りているかは分からない（実測。道具検証の記録 §9）。
#   import を範囲から外していた章でも最後まで exit 0 を返し続けた。
#   G5 の緑を「コードが正しい」ことの証拠に使わない。
#
# 終了コード: 0=PASS / 1=道具や材料の誤り / 2=FAIL（ズレあり）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# embedmd は Go 製で、この機械では PATH に無いことがある（道具検証の記録 §1）。
EMBEDMD="${EMBEDMD:-}"
if [[ -z "$EMBEDMD" ]]; then
  if command -v embedmd >/dev/null 2>&1; then
    EMBEDMD="$(command -v embedmd)"
  elif [[ -x "${GOPATH:-$HOME/go}/bin/embedmd" ]]; then
    EMBEDMD="${GOPATH:-$HOME/go}/bin/embedmd"
  else
    echo "FAIL: embedmd が見つからない。go install github.com/campoy/embedmd@latest で入れるか、" >&2
    echo "      EMBEDMD=/path/to/embedmd を環境変数で渡すこと" >&2
    exit 1
  fi
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
  echo "FAIL: 照合対象の章が1つも無い" >&2
  exit 1
fi

# ★ 変数を全角文字の直前に置くときは必ず ${} で囲む。
#   $EMBEDMD） と書くと bash が全角の一部を変数名に取り込んで「未割り当て」で落ちる
#   （g6-run.sh でも同じ罠を踏んでいる。道具検証の記録 §11）
echo "G5 引用ゲート: ${#TARGETS[@]} 件を照合する（embedmd: ${EMBEDMD}）"
cd "$ROOT"
if "$EMBEDMD" -d "${TARGETS[@]}"; then
  echo "G5 PASS（ただし引用範囲の過不足は見ていない）"
else
  echo "G5 FAIL: 教材のコードと listings/ の実ファイルがズレている" >&2
  echo "  直すには embedmd -w で教材側を実ファイルに合わせる" >&2
  exit 2
fi
