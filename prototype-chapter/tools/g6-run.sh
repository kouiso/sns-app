#!/usr/bin/env bash
# G6 実走ランナー（10 §4 G6 / 16 A5）
#
# 章を「文脈ゼロの実行体」に渡して走らせる。
# 知識の隔離が要件なので、リポジトリの外へ材料を出してから実行する。
# sns-app 配下で走らせると CLAUDE.md と SessionStart hook が設計文脈を注入して隔離が破れる。
#
# 使い方:
#   tools/g6-run.sh <章ID> read   ← 読み手の設問（面白さの比較評価）
#   tools/g6-run.sh <章ID> exec   ← 実走（手順どおりに動かして詰まりを出す）
#
# 必要なファイル:
#   chapter-<章ID>.md         教材本文
#   chapter-<章ID>-plain.md   比較用（対話を抜いた手順書調）… read のときだけ
#   snapshots/<前章ID>/       章開始時点のスターター… exec のとき、2章目以降
#
# 終了コード: 0=PASS / 1=引数や材料の誤り / 2=FAIL
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHAPTER="${1:-}"
MODE="${2:-}"
# read は本物の置き場所を半々に入れ替えるので、体数は偶数でなければ釣り合わない。
# 奇数だと、順番の偏りだけで本物が過半数を取れてしまう（実測: 中身が同じ2本で 2/3 が出た）。
N="${G6_READERS:-4}"

[[ -z "$CHAPTER" || -z "$MODE" ]] && { echo "usage: $(basename "$0") <章ID> read|exec" >&2; exit 1; }

BODY="$ROOT/chapter-$CHAPTER.md"
[[ -f "$BODY" ]] || { echo "FAIL: $BODY が無い" >&2; exit 1; }

# ★ 隔離: リポジトリの外へ出す。ここを変えると G6 の前提が崩れる。
WORK="$(mktemp -d "${TMPDIR:-/tmp}/g6-$CHAPTER-XXXXXX")"
echo "作業場所（リポジトリ外）: $WORK"

case "$MODE" in
  read)
    (( N % 2 == 0 )) || { echo "FAIL: read の体数は偶数にすること（G6_READERS=$N）" >&2; exit 1; }
    PLAIN="$ROOT/chapter-$CHAPTER-plain.md"
    [[ -f "$PLAIN" ]] || { echo "FAIL: 比較用の $PLAIN が無い。本文から対話を抜いた版を用意する" >&2; exit 1; }
    # ★ 順番の偏りを打ち消す（2026-07-27 の較正で発覚）。
    # 中身が完全に同じ2本で試したところ、実行体は3体とも A を選び、
    # 2体が理由に「内容が同じなので先に読んだ A を選ぶ」と書いた。
    # 常に本物を A に置くと、判定が中身ではなく置き場所で決まる。
    # よって実行体ごとに本物の位置を入れ替え、どちらに置いたかを REAL に記録して集計する。
    for i in $(seq 1 "$N"); do
      D="$WORK/r$i"; mkdir -p "$D"
      if (( i % 2 == 1 )); then
        cp "$BODY" "$D/A.md"; cp "$PLAIN" "$D/B.md"; echo "A" > "$D/REAL"
      else
        cp "$PLAIN" "$D/A.md"; cp "$BODY" "$D/B.md"; echo "B" > "$D/REAL"
      fi
    done
    cat > "$WORK/prompt.txt" <<'EOF'
あなたはプログラミング未経験の社会人です。SNS アプリを自分で作れるようになりたくて、
教材を探しています。

このディレクトリにある A.md と B.md を読んでください。
どちらも「ある教材の1章目」です。それ以外のファイルは見ないでください。

読み終えたら、次の3問に答えてください。あなたは読者であって批評家ではありません。

Q5. どちらの教材を買いますか。A か B か、どちらか一方を必ず選び、理由を1文で。
Q6. A を読んでいる間、退屈だと感じた箇所はどこですか。無ければ「無し」。
Q7. B を読んでいる間、退屈だと感じた箇所はどこですか。無ければ「無し」。

出力は次の形式だけにしてください。

Q5: A／B — ...
Q6: ...
Q7: ...
EOF
    ;;
  exec)
    cp "$BODY" "$WORK/chapter.md"
    # 章開始時点のスターターだけを渡す。設計書・開発ログ・listings は渡さない。
    PREV="${G6_PREV_SNAPSHOT:-}"
    if [[ -n "$PREV" ]]; then
      [[ -d "$PREV" ]] || { echo "FAIL: スターター $PREV が無い" >&2; exit 1; }
      mkdir -p "$WORK/start" && cp -R "$PREV/." "$WORK/start/"
      rm -f "$WORK/start/SNAPSHOT.txt"
      echo "スターター: $PREV"
    fi
    cat > "$WORK/prompt.txt" <<'EOF'
あなたはプログラミング未経験の学習者です。chapter.md だけを読み、書いてある手順を
そのとおりに実行してください。start/ があれば、それが前の章までの完成状態です。

守ること:
- chapter.md に書いていない知識で補ってはいけません。書いていないことは「詰まった」として記録します。
- 詰まっても、自分の知識で先回りして解決しないでください。何が起きたかを記録します。
- 対話型のコマンド（QR を端末で読む等）は実行できないので「実行できない」と記録します。

最後に次の形式で報告してください。

R1-到達: 章の最後の状態に到達できたか（できた／できなかった）
R2-詰まった箇所: 手が止まった箇所を、章のどの記述かが分かる形で列挙。無ければ「無し」
R3-教材外の知識で補った箇所: 章に書いていないことを自分の知識で埋めた箇所を列挙。無ければ「無し」
R4-実行できなかった手順: 端末操作など、この環境で実行できなかった手順。無ければ「無し」
EOF
    ;;
  *) echo "usage: $(basename "$0") <章ID> read|exec" >&2; exit 1 ;;
esac

# 別ファミリーの実行体を N 体、並行で走らせる
CODEX_ARGS=(--skip-git-repo-check)
if [[ "$MODE" == "exec" ]]; then
  # 実走は手順どおりにコマンドを打つ必要がある。承認待ちで止まると実走にならないため、
  # 承認を外して走らせる。**閉じ込めは作業ディレクトリで行う** —
  # $WORK は mktemp で作ったリポジトリ外の空ディレクトリで、そこを cwd にして起動する。
  CODEX_ARGS+=(--dangerously-bypass-approvals-and-sandbox)
fi

cd "$WORK"
# read は実行体ごとに材料の置き方が違うので、それぞれの部屋を cwd にして起動する
run_round() {
  local suffix="$1"
  for i in $(seq 1 "$N"); do
    local dir="$WORK"
    [[ "$MODE" == "read" ]] && dir="$WORK/r$i"
    ( cd "$dir" && timeout 1800 codex exec "${CODEX_ARGS[@]}" "$(cat "$WORK/prompt.txt")" < /dev/null > "$WORK/${suffix}$i.txt" 2>&1 || true ) &
  done
  wait
}

# 本物に投票した数を数える。本物の置き場所は実行体ごとに違う（REAL に記録済み）。
count_real_votes() {
  local suffix="$1" c=0 v real
  for i in $(seq 1 "$N"); do
    v=$(awk '/tokens used/{f=1} f' "$WORK/${suffix}$i.txt" | grep -m1 -oE "^Q5: [AB]" | awk '{print $2}' || true)
    real=$(cat "$WORK/r$i/REAL" 2>/dev/null || echo A)
    [[ -n "$v" && "$v" == "$real" ]] && c=$((c+1))
  done
  echo "$c"
}

run_round out

echo "----- 回答 -----"
FAIL=0
for i in $(seq 1 "$N"); do
  echo "=== 実行体 $i ==="
  # プロンプトの echo と回答が同じ形なので、末尾側だけを採る。
  # 見出しだけでなく、その下にぶら下がる詳細行も出す（詰まりの中身はそこにある）。
  # BSD sed は \| の選択肢を解さないので -E を使う（macOS で実際に取り出せなかった）
  REPORT=$(awk '/tokens used/{f=1} f' "out$i.txt" | sed -nE '/^(Q5|R1-)/,$p')
  if [[ -z "$REPORT" ]]; then
    echo "（回答を取り出せなかった。out$i.txt を見ること）"
    FAIL=1
  else
    echo "$REPORT"
  fi
done

if [[ "$MODE" == "read" ]]; then
  # 合否: 本物が過半数で選ばれること（本物の置き場所は実行体ごとに入れ替えてある）
  VOTES=$(count_real_votes out)
  NEED=$(( N / 2 + 1 ))
  echo "----- 判定 -----"
  # ${N} と書くこと。全角の「（」が直後に来ると、$N だけでは変数名の切れ目にならない
  echo "本物の得票: ${VOTES} / ${N}（合格は ${NEED} 以上）"
  if [[ "$VOTES" -lt "$NEED" ]]; then
    FAIL=2
  elif [[ "$VOTES" -eq "$NEED" ]]; then
    # ★ ちょうど閾値ぴったりは、ばらつきの幅と同じで信用できない（実測で 2/3 と 3/3 が両方出た）。
    # もう1回だけ回して、2回とも閾値以上のときだけ合格にする。
    echo "得票が閾値ちょうど。もう1回まわして確かめる"
    run_round re
    VOTES2=$(count_real_votes re)
    echo "2回目の得票: ${VOTES2} / ${N}"
    [[ "$VOTES2" -ge "$NEED" ]] || FAIL=2
  fi
fi

if [[ "$MODE" == "exec" ]]; then
  # 合否: 全実行体が章の最後まで到達し、教材外の知識で補った箇所が無いこと。
  # 「進めたから PASS」にしない（16 A5）。補完はそれ自体が教材の欠落である。
  echo "----- 判定 -----"
  NG=0
  for i in $(seq 1 "$N"); do
    R=$(awk '/tokens used/{f=1} f' "out$i.txt")
    echo "$R" | grep -q "^R1-到達: できた" || { echo "実行体 ${i}: 章の最後まで到達していない"; NG=1; }
    echo "$R" | grep -qE "^R3-教材外の知識で補った箇所: *無し" || { echo "実行体 ${i}: 教材外の知識で補った箇所がある"; NG=1; }
  done
  [[ "$NG" -eq 0 ]] && echo "全実行体が到達・補完なし" || FAIL=2
fi

echo "生ログ: $WORK"
if [[ "$FAIL" -ne 0 ]]; then echo "FAIL"; exit 2; fi
echo "PASS"
