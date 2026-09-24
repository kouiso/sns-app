#!/usr/bin/env bash
# G3 の「開始状態混入検査」（10 §4 G3）。
# 開始状態（スターター）に、その先の章で読者が書くはずの完成コードが
# 混ざっていないかを見る（前作の「販売ZIPに完成品混入」対策）。
#
# 使い方:
#   tools/g3-start-state.sh --starter <dir|manifest> [章md …]
#
# 開始状態は G0 の未決項目で置き場が決まっていない（10 §3 L76-77）。
# --starter を付けないときは検査器側が 3（未判定）を返す。未判定は
# 「通した」とは違うので、このスクリプトは 0 に変換せず 3 のまま返す。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"

python3 "$REPO/scripts/curriculum-qa/check_start_state.py" "$@"
