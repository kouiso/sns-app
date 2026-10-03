#!/usr/bin/env bash
# G3 の「開発ログの存在確認」（10 §5 / D1-7）。
# curriculum/<章ID>.md があるのに dev-logs/<章ID>.md が無い章を止める。
# 例外・条件つきで通す余地は無い（D16-7）。
#
# 使い方:
#   tools/g3-dev-log.sh                  curriculum/ の章すべてを対象に検査
#   tools/g3-dev-log.sh <章ID> …         指定した章だけを検査
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"

python3 "$REPO/scripts/curriculum-qa/check_dev_log.py" "$@"
