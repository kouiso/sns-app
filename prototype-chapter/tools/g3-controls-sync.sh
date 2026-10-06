#!/usr/bin/env bash
# 旧試作名と D17 正本の plain 対照版が同一内容かを確認する。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check_pair() {
  local legacy="$1"
  local canonical="$2"
  if ! cmp -s "$legacy" "$canonical"; then
    echo "FAIL: plain 対照版が同期していない: $legacy != $canonical" >&2
    exit 1
  fi
}

check_pair "$ROOT/chapter-expo-first-screen-plain.md" "$ROOT/g6/expo-first-screen/plain.md"
check_pair "$ROOT/chapter-live-reload-plain.md" "$ROOT/g6/live-reload/plain.md"
echo "G3 plain 対照版同期 PASS: 2組"
