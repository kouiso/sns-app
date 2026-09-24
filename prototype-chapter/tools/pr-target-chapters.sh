#!/usr/bin/env bash
# PR の差分から G4 受領証を要求する章IDを拾う（D15-8-2:
# 「教材PRの対象章に受領証が存在すること」）。
#
# 対象は curriculum/<章ID>.md の追加・変更・改名（改名先の新しいID）。
# README.md は目次で章ではない、削除されたファイルには受領証を要求しても
# 仕方ない、curriculum/ 以外のファイルは章ではないので、いずれも出さない。
#
# 使い方:
#   tools/pr-target-chapters.sh <ベースSHA>
#
# 出力: 章IDを1行1件（ソート・重複なし）。対象が無ければ何も出さず 0 で
# 終わる。ベースのコミットが取れていない（浅い fetch 等）ときは 2。
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $0 <ベースSHA>" >&2
  exit 2
fi

BASE="$1"
if ! git rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null; then
  echo "❌ ベースのコミットが見つかりません: $BASE" >&2
  echo "   actions/checkout に fetch-depth: 0、またはベースSHAの明示 fetch が要ります" >&2
  exit 2
fi

# A=追加 M=変更。D(削除)は対象外。`--no-renames` で改名を旧D+新Aに分解する:
# D1-4 で章の改名は想定内の操作で、改名先の章にも受領証は要る。改名検出の
# まま R だと丸ごと落ちて、改名された章が受領証なしで通ってしまう。
# `base...HEAD` はマージベースとの差分なので PR で見える変更そのものになる。
changed="$(git diff --name-only --no-renames --diff-filter=AM "${BASE}...HEAD")"

printf '%s\n' "$changed" \
  | grep -E '^curriculum/[^/]+\.md$' \
  | grep -v '^curriculum/README\.md$' \
  | sed -E 's|^curriculum/([^/]+)\.md$|\1|' \
  | sort -u || true
