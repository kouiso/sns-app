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
# ★ この実装は素の `embedmd -d` で比較しており、**整形の違いだけで FAIL になる**。
#   A8 の3（整形後の文字列で比較する）と食い違っている。捨て試作では整形の揺れが
#   起きなかったため表面化していないだけ。本番の実装前に決める（16 B30）。
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
    echo "FAIL: embedmd が見つからない。go install github.com/campoy/embedmd@v1.0.0 で入れるか、" >&2
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
# ★ 後段で `cd "$ROOT"` する。相対パスのまま cd すると、リポジトリ直下から
#   `prototype-chapter/chapter.md` と渡された時に `prototype-chapter/prototype-chapter/...`
#   を探しにいく。読めるかの検査は通るのに、そのあと「指示が無い章」に落ちて
#   終了コード 2 を返していた（2026-07-28 に再現）。ここで絶対パスへ直す。
UNREADABLE=()
ABS=()
for f in "${TARGETS[@]}"; do
  if [[ -r "$f" ]]; then
    if [[ "$f" = /* ]]; then ABS+=("$f"); else ABS+=("$PWD/$f"); fi
  else
    UNREADABLE+=("$f")
  fi
done
if [[ ${#UNREADABLE[@]} -gt 0 ]]; then
  echo "G5 ERROR: 読めない章がある: ${UNREADABLE[*]}" >&2
  echo "  ズレの有無は判定していない。パスを確かめる" >&2
  exit 1
fi
TARGETS=("${ABS[@]}")

# ★ 変数を全角文字の直前に置くときは必ず ${} で囲む。
#   $EMBEDMD） と書くと bash が全角の一部を変数名に取り込んで「未割り当て」で落ちる
#   （g6-run.sh でも同じ罠を踏んでいる。道具検証の記録 §11）
echo "G5 引用ゲート: ${#TARGETS[@]} 件を照合する（embedmd: ${EMBEDMD}）"
cd "$ROOT"

# ★ 引用指示が1本も無い章は、embedmd にとって「照合するものが無い」＝ 0 で終わる。
#   つまり**指示を全部消すとこのゲートは素通りする**（2026-07-28 に再現させた）。
#   コードを載せているのに指示を書き忘れた章が、緑のまま通ってしまう。
#   そこで「1本も無い章」は落とす。本当にコードを引かない章（読み物だけの章）は、
#   `prototype-chapter/g5-exempt.txt`（免除簿）へ章のファイル名を書いて免除する。
#   免除した章は必ず名前を出す。黙って外さない。
# 免除簿は先に1回だけ解決する。EXEMPT_LIST を指定されたのに読めない場合は、
# 「免除が無い」と扱うと章が「指示なし」に落ちて 2（ズレ側）で返る。
# 読めないのは材料の問題なので 1 で止める。
LIST=""
if [[ -n "${EXEMPT_LIST:-}" ]]; then
  if [[ ! -r "$EXEMPT_LIST" ]]; then
    echo "G5 ERROR: 指定された免除簿が読めない: $EXEMPT_LIST" >&2
    exit 1
  fi
  LIST="$EXEMPT_LIST"
elif [[ -f "$ROOT/g5-exempt.txt" ]]; then
  LIST="$ROOT/g5-exempt.txt"
fi

NO_DIRECTIVE=()
EXEMPTED=()
for f in "${TARGETS[@]}"; do
  # ★ 書式を丸ごと見る。`[embedmd]` とだけ書いた壊れた行を指示として数えると、
  #   embedmd 側は指示ゼロとみなして 0 で終わり、このゲートが PASS を出す。
  #   「指示が1本も無い章を落とす」ために足した検査が、逆に偽の緑を作っていた
  #   （2026-07-28 に再現）。正しい書式は `[embedmd]:# (パス ...)` である。
  grep -qE '^\[embedmd\]:# *\(' "$f" && continue
  # 免除は**章の本文では宣言しない**。別ファイル（免除簿）に章の名前を書く。
  #
  # ★ 以前は本文へ <!-- g5:no-listings 理由 --> と書く形にしていた。これは3回続けて
  #   迂回された（コード例の中／`~~~` の囲み／字下げした囲み／閉じ記号の判定漏れ）。
  #   原因は「本文の中に免除の合図を置いた」ことそのものである。教材はコードを載せる
  #   ものなので、本文のどこかに現れた文字列で免除が決まる限り、Markdown の書式を
  #   どれだけ正確に解析しても、例として書いた文字列と本物の宣言を区別し切れない。
  #   そこで**判定の材料を本文の外へ出した**。章のファイルを何も読まずに免除が決まる。
  if [[ -n "$LIST" ]]; then
    # 1行 = 「章のファイル名 <TAB> 理由」。理由が空の行は免除として認めない。
    # 名前だけで外せると、理由を誰も書かないまま章がゲートから消える。
    if awk -F'\t' -v want="$(basename "$f")" '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        $1 == want {
          reason = $2
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", reason)
          if (reason != "") { ok = 1 }
          else { bad = 1 }
        }
        END { if (bad && !ok) exit 2; exit !ok }
      ' "$LIST"; then
      EXEMPTED+=("$f")
      continue
    elif [[ $? -eq 2 ]]; then
      echo "G5 ERROR: 免除簿に理由の無い行がある: $(basename "$f")" >&2
      echo "  1行に「章のファイル名 <TAB> 理由」を書くこと" >&2
      exit 1
    fi
  fi
  NO_DIRECTIVE+=("$f")
done

if [[ ${#EXEMPTED[@]} -gt 0 ]]; then
  echo "G5 注意: 引用の照合を免除した章がある: ${EXEMPTED[*]}"
  echo "  この章のコードは誰も照合していない。免除の理由を人が読んで妥当か判断すること"
fi

if [[ ${#NO_DIRECTIVE[@]} -gt 0 ]]; then
  echo "G5 FAIL: 引用指示が1本も無い章がある: ${NO_DIRECTIVE[*]}" >&2
  echo "  コードを載せるなら [embedmd]:# (パス ...) の形で指示を書く。" >&2
  echo "  引用しない章なら prototype-chapter/g5-exempt.txt へ章のファイル名と理由を書く" >&2
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

  # 出力が1文字も無いのに非ゼロで終わったのは、差分ではなく道具側の異常
  # （強制終了・クラッシュ）。ズレと呼ぶと教材を直しにいくことになる。
  if [[ -z "$OUT" ]]; then
    BROKEN+=("$f")
    continue
  fi

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
