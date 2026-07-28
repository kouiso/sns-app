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
# 終了コード: 0=PASS / 1=道具や材料の誤り
#             2=ゲート不合格（ズレがある、または引用指示が無い／免除されている）
#             ★ 2 は「ズレ」だけを意味せん。指示の書き忘れでも 2 が返る。
#               どちらかは出力の文言で分かる。
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
# ★ -r だけでは足りん。`chapter-x.md -> /dev/zero` のようなリンクも -r を通る。
#   そのまま grep へ渡すと**終わらん**（無限にゼロを読み続ける）。
#   全PRで走る CI ジョブがそこで止まる。通常ファイルであることも確かめる。
UNREADABLE=()
ABS=()
for f in "${TARGETS[@]}"; do
  if [[ -f "$f" && -r "$f" ]]; then
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
#   そこで「1本も無い章」は落とす。
#   本当にコードを引かない章（読み物だけの章）が出てきた時は、
#   人の承認を挟んで扱いを決める。いま自動で外せる経路は用意していない。
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

# ★ 免除は現在いっさい認めていない。よって**章ごとに引く前に、簿を丸ごと**検査する。
#   章ごとに引くと、引用指示のある章に対応する古い行が「素通り」して残り続ける。
#   その章から指示が消えた日に、誰も気づかんまま古い行が効き始める。
#   簿に1行でもあれば、その章の状態に関係なく落とす。
if [[ -n "$LIST" ]]; then
  # ★ 簿が全部コメントだと grep -v は「1件も無い」で非ゼロを返す。
  #   set -e と pipefail が効いているので、|| true が無いとここで落ちる。
  STALE="$(grep -vE '^[[:space:]]*(#|$)' "$LIST" | cut -f1 | tr '\n' ' ' || true)"
  if [[ -n "${STALE// /}" ]]; then
    echo "G5 FAIL: 免除簿に行がある: ${STALE}" >&2
    echo "  免除はいま認めていない。行を消すか、人の承認を挟む形で設計し直すこと" >&2
    echo "  （章に引用指示があっても、簿に残った行は古くなって効き始めるので落とす）" >&2
    exit 2
  fi
fi

NO_DIRECTIVE=()
for f in "${TARGETS[@]}"; do
  # ★ 書式を丸ごと見る。`[embedmd]` とだけ書いた壊れた行を指示として数えると、
  #   embedmd 側は指示ゼロとみなして 0 で終わり、このゲートが PASS を出す。
  #   「指示が1本も無い章を落とす」ために足した検査が、逆に偽の緑を作っていた
  #   （2026-07-28 に再現）。正しい書式は `[embedmd]:# (パス ...)` である。
  grep -qE '^\[embedmd\]:# *\(' "$f" && continue
  NO_DIRECTIVE+=("$f")
done

if [[ ${#NO_DIRECTIVE[@]} -gt 0 ]]; then
  echo "G5 FAIL: 引用指示が1本も無い章がある: ${NO_DIRECTIVE[*]}" >&2
  echo "  コードを載せるなら [embedmd]:# (パス ...) の形で指示を書く。" >&2
  echo "  引用しない読み物の章なら、人の承認を経て扱いを決めること（自動で外す経路は無い）" >&2
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
