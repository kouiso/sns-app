#!/usr/bin/env bash
# prh 辞書の検知テスト（12 §3-3 / 10:144「辞書は行を足すたびに検知テストを回す」）
#
#   positive.md              … 12 §2.1 の禁止6カテゴリ＋13 §5 の不採用スタック名の陽性例。
#                              「磯貝「…」」で始まる行と「- **」で始まる行が検査対象で、
#                              1行でも検出漏れがあれば FAIL。
#   negative.md              … 正常な教材本文と、禁止パターンに似た正常な言い回し。
#                              1件でも検出されたら FAIL（誤検知ゼロの確認。前作#15 対策）。
#   check-tone-patterns.md   … 前作 scripts/curriculum-qa/check_tone.py の32パターンを
#                              1行ずつ並べたもの。移植不要（D8-3）の根拠をここで維持する。
#
# 終了コード: 0=全部通過 / 1=検出漏れか誤検知あり
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEXTLINT="$ROOT/node_modules/.bin/textlint"
HERE="$ROOT/prh/testdata"
rc=0

if [[ ! -x "$TEXTLINT" ]]; then
  echo "FAIL: textlint が無い。$ROOT で npm ci を先に実行すること" >&2
  exit 1
fi

check_positive() {
  local file="$1"
  local hits
  hits="$("$TEXTLINT" -f compact "$file" 2>/dev/null | sed -n 's/.*: line \([0-9]*\),.*/\1/p' | sort -n -u)"
  local total=0 missed=0
  while IFS= read -r pair; do
    local n="${pair%%:*}" line="${pair#*:}"
    case "$line" in
      磯貝*|'- **'*) ;;
      *) continue ;;
    esac
    total=$((total + 1))
    if ! grep -qx "$n" <<<"$hits"; then
      missed=$((missed + 1))
      echo "  検出漏れ 行$n: $line"
    fi
  done < <(grep -n '' "$file")
  echo "陽性 $file: $((total - missed))/$total 検出"
  [[ $missed -eq 0 ]] || rc=1
}

check_positive "$HERE/positive.md"
check_positive "$HERE/check-tone-patterns.md"

if "$TEXTLINT" "$HERE/negative.md" >/dev/null 2>&1; then
  echo "陰性 $HERE/negative.md: 誤検知 0 件"
else
  echo "  誤検知あり:"
  "$TEXTLINT" -f compact "$HERE/negative.md"
  rc=1
fi

[[ $rc -eq 0 ]] && echo "prh 検知テスト PASS" || echo "prh 検知テスト FAIL" >&2
exit $rc
