#!/usr/bin/env bash
# G4 受領証の機械検査（D15-8）。
# material/reviews/g4/ の受領証が様式を満たして記入済みかを見る。
#
# 使い方:
#   tools/g4-receipt.sh              g4/ にある受領証すべてを検査
#   tools/g4-receipt.sh <章ID> …     その章の受領証が在ることも要求する
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"

ARGS=()
for a in "$@"; do
  ARGS+=(--target "$a")
done
# ${ARGS[@]+...} は空配列でも bash 3.2 の set -u で落ちない書き方。
# "${ARGS[@]}" だけだと macOS の /bin/bash（3.2）で unbound variable になる。
python3 "$REPO/scripts/curriculum-qa/check_g4_receipt.py" ${ARGS[@]+"${ARGS[@]}"}
