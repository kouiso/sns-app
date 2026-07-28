#!/usr/bin/env bash
# G5 引用ゲート（10 §4 G5）
#
# 教材に貼ったコードが listings/ の実ファイルとズレていないかを embedmd で照合する。
#
# 使い方:
#   tools/g5-quote.sh              章の本文すべてを照合する
#   tools/g5-quote.sh chapter.md   ファイルを指定して照合する
#
# ★ embedmd -d の終了コードは 1 ではなく 2 である（実測。道具検証の記録 §3）。
#   判定を「exit 1 なら FAIL」と書くとズレを見逃すため、非ゼロを FAIL として扱う。
#
# ★ このゲートが緑でも、引用範囲が足りているかは分からない（実測。道具検証の記録 §9）。
#   import を範囲から外していた章でも最後まで exit 0 を返し続けた。
#   G5 の緑を「コードが正しい」ことの証拠に使わない。
#
# 終了コード: 0=PASS / 1=道具や材料の誤り / 2=FAIL（ズレあり）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# embedmd は Go 製で、この機械では PATH に無いことがある（道具検証の記録 §1）。
EMBEDMD="${EMBEDMD:-}"
if [[ -z "$EMBEDMD" ]]; then
  if command -v embedmd >/dev/null 2>&1; then
    EMBEDMD="$(command -v embedmd)"
  elif [[ -x "${GOPATH:-$HOME/go}/bin/embedmd" ]]; then
    EMBEDMD="${GOPATH:-$HOME/go}/bin/embedmd"
  else
    echo "FAIL: embedmd が見つからない。go install github.com/campoy/embedmd@latest で入れるか、" >&2
    echo "      EMBEDMD=/path/to/embedmd を環境変数で渡すこと" >&2
    exit 1
  fi
fi

if [[ $# -gt 0 ]]; then
  TARGETS=("$@")
else
  TARGETS=()
  for f in "$ROOT"/chapter*.md; do
    [[ -e "$f" ]] || continue
    [[ "$f" == *-plain.md ]] && continue
    TARGETS+=("$f")
  done
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "FAIL: 照合対象の章が1つも無い" >&2
  exit 1
fi

# ★ 引数で渡されたファイルが読めるかを、判定に入る前に確かめる。
#   ここを飛ばすと、存在しないファイルが後段の「引用指示が無い章」に落ちて
#   終了コード 2（＝引用のズレ）で報告される。ズレは1件も無いのに、である
#   （2026-07-28 に再現させた）。読めないのは材料の問題なので 1 で返す。
UNREADABLE=()
for f in "${TARGETS[@]}"; do
  [[ -r "$f" ]] || UNREADABLE+=("$f")
done
if [[ ${#UNREADABLE[@]} -gt 0 ]]; then
  echo "G5 ERROR: 読めない章がある: ${UNREADABLE[*]}" >&2
  echo "  ズレの有無は判定していない。パスを確かめる" >&2
  exit 1
fi

# ★ 変数を全角文字の直前に置くときは必ず ${} で囲む。
#   $EMBEDMD） と書くと bash が全角の一部を変数名に取り込んで「未割り当て」で落ちる
#   （g6-run.sh でも同じ罠を踏んでいる。道具検証の記録 §11）
echo "G5 引用ゲート: ${#TARGETS[@]} 件を照合する（embedmd: ${EMBEDMD}）"
cd "$ROOT"

# ★ 引用指示が1本も無い章は、embedmd にとって「照合するものが無い」＝ 0 で終わる。
#   つまり**指示を全部消すとこのゲートは素通りする**（2026-07-28 に再現させた）。
#   コードを載せているのに指示を書き忘れた章が、緑のまま通ってしまう。
#   そこで「1本も無い章」は落とす。本当に code を引かない章
#   （読み物だけの章）は、本文へ次の1行を書いて明示的に免除する。
#     <!-- g5:no-listings この章は listings/ から引用しない -->
#   免除は「本文の地の文に置かれた1行」だけを認める。コード例の中に同じ文字列が
#   出てきても免除にしない（教材はコードを載せるものなので、例として書いた文字列で
#   ゲートが外れると気づけない）。免除した章は必ず名前を出す。黙って外さない。
NO_DIRECTIVE=()
EXEMPTED=()
for f in "${TARGETS[@]}"; do
  grep -q '^\[embedmd\]' "$f" && continue
  # 囲みの中を落としてから免除の宣言を探す。
  # ★ Markdown の囲みは ``` だけではない。~~~ も使えるし、行頭に空白3つまでなら
  #   字下げしても囲みとして成立する。行頭の ``` だけを見ていた実装では、
  #   ~~~ の中や字下げした ``` の中に書いた宣言が免除として通った
  #   （2026-07-28 に両方とも再現させた）。
  #   閉じ記号は開き記号と同じ文字で、同じ長さ以上でなければならない。
  if awk '
      {
        line = $0
        sub(/^ {0,3}/, "", line)
        if (match(line, /^(`{3,}|~{3,})/)) {
          marker = substr(line, 1, RLENGTH)
          char = substr(marker, 1, 1)
          if (!infence) { infence = 1; fchar = char; flen = RLENGTH; next }
          if (char == fchar && RLENGTH >= flen) { infence = 0; next }
          next
        }
      }
      !infence && /<!-- *g5:no-listings +[^ ->]/ { found = 1 }
      END { exit !found }
    ' "$f"; then
    EXEMPTED+=("$f")
    continue
  fi
  NO_DIRECTIVE+=("$f")
done

if [[ ${#EXEMPTED[@]} -gt 0 ]]; then
  echo "G5 注意: 引用の照合を免除した章がある: ${EXEMPTED[*]}"
  echo "  この章のコードは誰も照合していない。免除の理由を人が読んで妥当か判断すること"
fi

if [[ ${#NO_DIRECTIVE[@]} -gt 0 ]]; then
  echo "G5 FAIL: 引用指示が1本も無い章がある: ${NO_DIRECTIVE[*]}" >&2
  echo "  コードを載せるなら [embedmd]: 指示を書く。" >&2
  echo "  引用しない章なら本文へ <!-- g5:no-listings 理由 --> を書いて免除する" >&2
  echo "  （理由は必須。コード例の中に書いても免除にならない）" >&2
  exit 2
fi
# ★ 「ズレを見つけた」と「照合そのものが失敗した」を区別する。
#   embedmd v1.0.0 は**どちらの場合も終了コード 2 を返す**（2026-07-28 に実測）。
#   終了コードでは分けられないので、出力の形で分ける。
#     差分の行  … `@@` `+` `-` 半角空白 のいずれかで始まる
#     失敗の行  … それ以外（`ファイル名:行番号: could not read ...` 等）
#
#   ★★ 章を1回でまとめて渡すと、片方がズレ・もう片方が読めない時に
#   出力へ両方が混ざる。`@@` があるかどうかだけ見ると「ズレ」と報告してしまい、
#   読めないファイルが隠れる（2026-07-28 に再現させた）。
#   よって**章ごとに1回ずつ**判定し、**失敗はズレより強い**として扱う。

DRIFT=()
BROKEN=()

for f in "${TARGETS[@]}"; do
  set +e
  OUT="$("$EMBEDMD" -d "$f" 2>&1)"
  ST=$?
  set -e

  [[ -n "$OUT" ]] && printf '%s\n' "$OUT"
  [[ $ST -eq 0 ]] && continue

  # 差分として説明できない行が1本でもあれば、照合が成立していない
  if grep -qv '^[ @+-]' <<<"$(grep -v '^$' <<<"$OUT")"; then
    BROKEN+=("$f")
  else
    DRIFT+=("$f")
  fi
done

if [[ ${#BROKEN[@]} -gt 0 ]]; then
  echo "G5 ERROR: 照合そのものが失敗した章がある: ${BROKEN[*]}" >&2
  echo "  この章のズレの有無は判定できていない。上の出力を読んで原因を直す" >&2
  [[ ${#DRIFT[@]} -gt 0 ]] && echo "  （別にズレも出ている章がある: ${DRIFT[*]}）" >&2
  exit 1
elif [[ ${#DRIFT[@]} -gt 0 ]]; then
  echo "G5 FAIL: 教材のコードと listings/ の実ファイルがズレている: ${DRIFT[*]}" >&2
  echo "  直すには embedmd -w で教材側を実ファイルに合わせる" >&2
  exit 2
else
  echo "G5 PASS（ただし引用範囲の過不足は見ていない）"
fi
