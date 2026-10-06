#!/usr/bin/env bash
# G3 の5検査を束ねる Phase 2 / P1 / G1 前の暫定入口。
#
# 正式運用には、凍結済み開始状態 manifest と dev-logs/<章ID>.md が必要。
# この入口の PASS は検知テスト結果であり、P1/G1 承認や正式 G3 通過の代用にならない。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
START_STATE_MANIFEST="$ROOT/g3-start-state.trial.json"
DEV_LOGS_DIR="$ROOT/../dev-logs"
TARGETS=()

usage() {
  echo "usage: tools/g3-full.sh [--start-state-manifest PATH] [--dev-logs-dir PATH] [chapter.md ...]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-state-manifest)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      START_STATE_MANIFEST="$2"
      shift 2
      ;;
    --dev-logs-dir)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      DEV_LOGS_DIR="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --*)
      echo "FAIL: 未知の引数 $1" >&2
      usage
      exit 2
      ;;
    *)
      TARGETS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  for file in "$ROOT"/chapter*.md; do
    [[ -e "$file" ]] || continue
    TARGETS+=("$file")
  done
fi

if [[ ! -f "$START_STATE_MANIFEST" ]]; then
  echo "FAIL: 開始状態 manifest が無い: $START_STATE_MANIFEST" >&2
  exit 1
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "FAIL: 検査対象の章が1つも無い" >&2
  exit 1
fi

echo "暫定 G3: 文体チェック ${#TARGETS[@]} 件"
"$ROOT/tools/g3-style.sh" "${TARGETS[@]}"

echo "暫定 G3: 構造・開始状態・方針同期・開発ログ存在"
python3 "$ROOT/tools/g3_checks.py" \
  --start-state-manifest "$START_STATE_MANIFEST" \
  --dev-logs-dir "$DEV_LOGS_DIR" \
  "${TARGETS[@]}"

echo "暫定 G3 5検査 PASS（P1/G1 前。正式 G3 通過証拠ではない）"
