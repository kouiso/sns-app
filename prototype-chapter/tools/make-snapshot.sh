#!/usr/bin/env bash
# A7 章末スナップショット生成（16 A7 / 10 §4）
#
# listings/<章ID>/ を「読者へ渡せる状態」に固めて snapshots/<章ID>/ を作る。
# 生成物には再取得できるもの（node_modules 等）を含めない。
#
# 使い方:  tools/make-snapshot.sh <章ID>
#          tools/make-snapshot.sh <章ID> --verify   ← 別の場所で npm ci が通るかまで見る
#
# 終了コード: 0=成功 / 1=引数や対象の誤り / 2=検証失敗
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHAPTER="${1:-}"
VERIFY="${2:-}"

if [[ -z "$CHAPTER" ]]; then
  echo "usage: $(basename "$0") <章ID> [--verify]" >&2
  exit 1
fi

SRC="$ROOT/listings/$CHAPTER"
DST="$ROOT/snapshots/$CHAPTER"

if [[ ! -d "$SRC" ]]; then
  echo "FAIL: listings/$CHAPTER が無い" >&2
  exit 1
fi

# 再取得できるもの・機械固有のものは持ち出さない
EXCLUDES=(node_modules .expo .expo-shared dist ios android .git .DS_Store)
# ★ AI 向けの指示ファイルも持ち出さない。
# create-expo-app のテンプレートが AGENTS.md / CLAUDE.md / .claude を作るため、
# 何もしないと読者へ渡すスナップショットに制作側の指示が混入する（実際に混入した）。
EXCLUDES+=(AGENTS.md CLAUDE.md .claude .cursor .github/copilot-instructions.md)

rm -rf "$DST"
mkdir -p "$DST"

RSYNC_ARGS=()
for e in "${EXCLUDES[@]}"; do RSYNC_ARGS+=(--exclude "$e"); done
rsync -a "${RSYNC_ARGS[@]}" "$SRC/" "$DST/"

# 依存の版を固定するため package-lock.json は必須にする。
# これが無いと、読者の手元と教材で入るものが変わる（B16 と同じ問題）。
if [[ ! -f "$DST/package-lock.json" ]]; then
  echo "FAIL: package-lock.json が無い。版が固定できないので配れない" >&2
  exit 2
fi

# 目録を作る。中身が変わればハッシュが変わるので、章末の状態を後から照合できる。
MANIFEST="$DST/SNAPSHOT.txt"
{
  echo "chapter: $CHAPTER"
  echo "files:"
  (cd "$DST" && find . -type f ! -name SNAPSHOT.txt | sort | while read -r f; do
    printf "  %s  %s\n" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "${f#./}"
  done)
} > "$MANIFEST"

COUNT=$(grep -c '^  ' "$MANIFEST" || true)
echo "OK: snapshots/$CHAPTER ($COUNT ファイル)"

if [[ "$VERIFY" == "--verify" ]]; then
  # 「その場だけで成立するか」を、リポジトリの外の空のディレクトリで確かめる。
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  cp -R "$DST/." "$TMP/"
  if (cd "$TMP" && npm ci > "$TMP/npm.log" 2>&1); then
    echo "OK: 空のディレクトリで npm ci が通った"
  else
    echo "FAIL: 空のディレクトリで npm ci が通らない。読者の手元でも通らない" >&2
    tail -20 "$TMP/npm.log" >&2
    exit 2
  fi
fi
