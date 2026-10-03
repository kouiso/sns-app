#!/usr/bin/env bash
# ゲートの各検査を呼ぶ共通ラッパ。終了コード 3（未判定）の扱いを
# ここ1箇所に集約する（D1 §8-3: 対象0件は緑にしない、でも FAIL とも違う）。
#
#   0 → 0 のまま
#   3 → 0 に読み替える。GitHub Actions 上では ::warning を出す。
#       それ以外では ⏸️ の行を出す。
#   それ以外 → そのまま返す（1=違反、2=使い方の誤りは通す）
#
# 使い方:
#   tools/gate-step.sh <コマンド> [引数…]
set -uo pipefail

"$@"
rc=$?
if [ "$rc" -eq 3 ]; then
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    echo "::warning title=未判定::$* — 成果物がまだ無いため未判定（終了コード3）"
  else
    echo "⏸️ 未判定: $*（終了コード3。合否には数えない）"
  fi
  exit 0
fi
exit "$rc"
