#!/usr/bin/env bash
# G6 runner. Read mode is provisional until knowledge and runtime isolation are
# independently proven. Exec mode is intentionally unavailable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHAPTER="${1:-}"
MODE="${2:-}"
N="${G6_READERS:-4}"
TIMEOUT_SECONDS="${G6_TIMEOUT_SECONDS:-1800}"
MODEL="${G6_MODEL:-gemini-3.8-flash}"

usage() {
  echo "usage: $(basename "$0") <章ID> read|exec" >&2
}

[[ -n "$CHAPTER" && -n "$MODE" ]] || { usage; exit 1; }
[[ "$N" =~ ^[1-9][0-9]*$ ]] || {
  echo "FAIL: G6_READERS must be a positive integer" >&2
  exit 1
}
[[ "$TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]] || {
  echo "FAIL: G6_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 1
}

if [[ "$MODE" == "exec" ]]; then
  echo "NOT_READY: exec requires an independently verified sandbox and objective validator" >&2
  echo "PROVISIONAL / NON-FORMAL G6: no exec result was produced" >&2
  exit 2
fi
[[ "$MODE" == "read" ]] || { usage; exit 1; }
(( N % 2 == 0 )) || {
  echo "FAIL: read の体数は偶数にすること（G6_READERS=$N）" >&2
  exit 1
}

BODY="$ROOT/chapter-$CHAPTER.md"
CONTROL_DIR="$ROOT/g6/$CHAPTER"
PLAIN="$CONTROL_DIR/plain.md"
MINUS="$CONTROL_DIR/minus.md"
DEV_LOGS_DIR="${G6_DEV_LOGS_DIR:-$ROOT/../dev-logs}"
DEV_LOG="$DEV_LOGS_DIR/$CHAPTER.md"

[[ -f "$BODY" ]] || { echo "FAIL: $BODY が無い" >&2; exit 1; }
[[ -f "$PLAIN" ]] || {
  echo "FAIL: 比較用の $PLAIN が無い。対話を抜いた版を用意する" >&2
  exit 1
}
head -n 5 "$PLAIN" | grep -q "抜いた要素" || {
  echo "FAIL: $PLAIN の先頭に抜いた要素のメタ行が無い" >&2
  exit 1
}

EVIDENCE="$(python3 "$ROOT/tools/g6_support.py" devlog "$DEV_LOG")" || exit 1
HIGH_VALUE_COUNT="$(printf '%s\n' "$EVIDENCE" | sed -n 's/^HIGH_VALUE_COUNT=//p')"
CLASSIFIED_ITEM_COUNT="$(printf '%s\n' "$EVIDENCE" | sed -n 's/^CLASSIFIED_ITEM_COUNT=//p')"
DEV_LOG_SHA256="$(printf '%s\n' "$EVIDENCE" | sed -n 's/^DEV_LOG_SHA256=//p')"
[[ "$HIGH_VALUE_COUNT" =~ ^[0-9]+$ && "$CLASSIFIED_ITEM_COUNT" =~ ^[0-9]+$ && "$DEV_LOG_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "FAIL: 開発ログ証拠を解釈できない" >&2
  exit 1
}

if (( HIGH_VALUE_COUNT > 0 )); then
  [[ -f "$MINUS" ]] || {
    echo "FAIL: 高価値の詰まりが $HIGH_VALUE_COUNT 件あるため $MINUS が必要" >&2
    exit 1
  }
  head -n 5 "$MINUS" | grep -q "抜いた要素" || {
    echo "FAIL: $MINUS の先頭に抜いた要素のメタ行が無い" >&2
    exit 1
  }
fi

DROID_BIN="${DROID_BIN:-$(command -v droid || true)}"
[[ -n "$DROID_BIN" && -x "$DROID_BIN" ]] || {
  echo "NOT_READY: droid read adapter is unavailable" >&2
  exit 2
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/g6-$CHAPTER-XXXXXX")"
echo "作業場所（リポジトリ外）: $WORK"
echo "PROVISIONAL READ ONLY / NON-FORMAL G6"
echo "knowledge, filesystem, hooks, and network isolation are not independently proven"
echo "DEV_LOG_SHA256=$DEV_LOG_SHA256 HIGH_VALUE_COUNT=$HIGH_VALUE_COUNT CLASSIFIED_ITEM_COUNT=$CLASSIFIED_ITEM_COUNT"

cat > "$WORK/prompt.txt" <<'EOF'
あなたはプログラミング未経験の社会人です。SNS アプリを自分で作れるようになりたくて、
教材を探しています。

このディレクトリにある A.md と B.md だけを読んでください。
どちらも同じ教材の同じ章の候補です。それ以外のファイルは見ないでください。

Q5. どちらの教材を買いますか。A か B か、どちらか一方を必ず選び、理由を1文で。
Q6. A を読んでいる間、退屈だと感じた箇所はどこですか。無ければ空配列。
Q7. B を読んでいる間、退屈だと感じた箇所はどこですか。無ければ空配列。

JSONオブジェクトだけを返してください。
{"adapter":"droid-gemini-read","choice":"A","reason":"理由を1文で書く","boring_a":[],"boring_b":[]}
EOF

declare -a PIDS STATUS
NEED=$((N / 2 + 1))

prepare_round() {
  local comparison="$1" i room
  for i in $(seq 1 "$N"); do
    room="$WORK/r$i"
    mkdir -p "$room"
    if (( i % 2 == 1 )); then
      cp "$BODY" "$room/A.md"
      cp "$comparison" "$room/B.md"
    else
      cp "$comparison" "$room/A.md"
      cp "$BODY" "$room/B.md"
    fi
  done
}

run_attempt() {
  local round="$1" attempt="$2" i room
  PIDS=()
  STATUS=()
  for i in $(seq 1 "$N"); do
    room="$WORK/r$i"
    (
      cd "$room"
      G6_ROUND="$round" G6_ATTEMPT="$attempt" G6_PARTICIPANT="$i" \
        timeout "$TIMEOUT_SECONDS" "$DROID_BIN" exec \
          --model "$MODEL" \
          --reasoning-effort medium \
          --only-tools Read \
          --disable-builtin-skills \
          -f "$WORK/prompt.txt" \
          < /dev/null > "$WORK/$round-$attempt-$i.json" 2>&1
    ) &
    PIDS[i]=$!
  done
  for i in $(seq 1 "$N"); do
    if wait "${PIDS[$i]}"; then
      STATUS[i]=0
    else
      STATUS[i]=$?
    fi
  done
}

validate_attempt() {
  local round="$1" attempt="$2" i result
  for i in $(seq 1 "$N"); do
    if [[ "${STATUS[$i]:-1}" -ne 0 ]]; then
      echo "FAIL: $round attempt $attempt participant $i exited ${STATUS[$i]}" >&2
      return 1
    fi
    result="$WORK/$round-$attempt-$i.json"
    if ! python3 "$ROOT/tools/g6_support.py" read < "$result" >/dev/null 2>&1; then
      echo "FAIL: $round attempt $attempt participant $i returned invalid JSON" >&2
      return 1
    fi
  done
}

count_real_votes() {
  local round="$1" attempt="$2" i choice real count=0
  for i in $(seq 1 "$N"); do
    choice="$(
      python3 "$ROOT/tools/g6_support.py" read \
        < "$WORK/$round-$attempt-$i.json" |
        sed -n 's/^CHOICE=//p'
    )"
    if (( i % 2 == 1 )); then real="A"; else real="B"; fi
    [[ "$choice" == "$real" ]] && count=$((count + 1))
  done
  printf '%s\n' "$count"
}

show_attempt() {
  local round="$1" attempt="$2" i
  echo "----- $round attempt $attempt responses -----"
  for i in $(seq 1 "$N"); do
    printf 'participant %s: ' "$i"
    cat "$WORK/$round-$attempt-$i.json"
    printf '\n'
  done
}

evaluate_round() {
  local round="$1" comparison="$2" attempt=1 votes
  prepare_round "$comparison"
  run_attempt "$round" "$attempt"
  validate_attempt "$round" "$attempt" || return 1
  show_attempt "$round" "$attempt"
  votes="$(count_real_votes "$round" "$attempt")"
  echo "$round real votes: $votes / $N (need $NEED)"
  (( votes >= NEED )) || return 1

  if (( votes == NEED )); then
    attempt=2
    echo "$round reached the exact threshold; retrying the same comparison"
    prepare_round "$comparison"
    run_attempt "$round" "$attempt"
    validate_attempt "$round" "$attempt" || return 1
    show_attempt "$round" "$attempt"
    votes="$(count_real_votes "$round" "$attempt")"
    echo "$round retry real votes: $votes / $N (need $NEED)"
    (( votes >= NEED )) || return 1
  fi
}

FAIL=0
if ! evaluate_round plain "$PLAIN"; then
  echo "FAIL: plain round" >&2
  FAIL=2
fi

if [[ "$FAIL" -eq 0 ]]; then
  if (( HIGH_VALUE_COUNT == 0 )); then
    echo "R2=N/A HIGH_VALUE_COUNT=0 CLASSIFIED_ITEM_COUNT=$CLASSIFIED_ITEM_COUNT DEV_LOG_SHA256=$DEV_LOG_SHA256"
  elif ! evaluate_round minus "$MINUS"; then
    echo "FAIL: minus round" >&2
    FAIL=2
  fi
fi

echo "生ログ: $WORK"
if [[ "$FAIL" -ne 0 ]]; then
  echo "PROVISIONAL_FAIL / NON-FORMAL G6"
  exit 2
fi
echo "PROVISIONAL_PASS / NON-FORMAL G6"
