#!/usr/bin/env python3
"""コードブロックの書き込み先が、そのブロックだけを見て分かるかを見る。

読者は1日分を頭から順に読むとは限らない。目次のリンクから飛んでくるし、詰まった日だけを
後から開き直す。そのとき `// filepath: 続き` とだけ書いてあると、何の続きなのか分からない。
上へ遡って最初に見つかるファイル名が正解とも限らず、実測では156行上の読み比べ用コードを
指しているように読める箇所があった。

判定は「`// filepath:` の値が指示語だけで終わっていないか」に絞る。実ファイル名が入って
いれば、続きであることを添えていても通す。散文側の「上のコード」「さきほど」は語の形が
一定せず機械では判定できないので、この検査の対象にしない。

実ファイル名の判定は現行構成（Expo Router + Supabase）の `app/` `supabase/` に
置き換えてある。前作の `src/` `prisma/` `scripts/` は、現在のリポジトリに対応する
実体が無いため、実ファイル名としては数えない。

終了コード:
  0 = 判定でき、違反なし
  1 = 違反あり
  2 = 使い方の誤り・対象ファイルが無い
  3 = 未判定。「完成版に存在しない書き込み先」の検査は完成版ルートが要る。
      `--completed-root` が無い、またはリポジトリに完成版（app/ または supabase/）が
      まだ無い間はこの部分検査だけを未判定とし、それ以外の違反が無ければ 3 を返す。
"""

import re
import sys
from pathlib import Path

from curriculum_blocks import REAL_PREFIXES
from markdown_scan import fence_states

NOT_JUDGED = 3

FILEPATH = re.compile(r"^\s*(?:\{/\*\s*filepath:\s*(.+?)\s*\*/\}|(?://|#)\s*filepath:\s*(.+?))\s*$")


def filepath_value(match):
    # 2つの書き方を1つの正規表現で受けるため捕獲群が2本になる。どちらが埋まるかは
    # 書き方で決まるので、呼び出し側に群番号を意識させず値だけを返す。
    return match.group(1) if match.group(1) is not None else match.group(2)
# 「続き」「同上」だけで、どのファイルなのかを名乗っていない値。
# 「読み比べ用サンプル」は実ファイルを持たないと明言しているので通す。
VAGUE = re.compile(r"^(続き|同上|前の続き|上記の続き|同じファイル)[（(]?[^）)]*[）)]?$")
# 同じ注記が2回以上ぶら下がった値。実測で、上の行を書き換えながら下の行を作る処理が
# 書き換え済みの値を拾い直し、`（同じファイルの続き）` が最大6回積み上がっていた。
# 指示語ではないので VAGUE では捕まらず、読者が写経する欄にそのまま残る。
REPEATED = re.compile(r"([（(][^）)]+[）)])\1")


def find(text: str) -> list[tuple[int, str]]:
    """(行番号, 値) を返す。行番号は1始まり。"""
    hits: list[tuple[int, str]] = []
    for i, line, state, _ in fence_states(text):
        if state != "inside":
            continue
        fp = FILEPATH.match(line)
        if fp and (VAGUE.match(filepath_value(fp)) or REPEATED.search(filepath_value(fp))):
            hits.append((i, filepath_value(fp)))
    return hits


def find_sample_with_real_path(text: str) -> list[tuple[int, str]]:
    """読み比べ用の節にあるのに、実ファイル名を名乗っているブロックを返す。

    「Before（改善前のコード）」「After（プロが書くコード）」の中のコードは、写経の対象では
    ない。実測では、続きのブロックだけが読み比べ用と書かれていて、先頭だけ実ファイル名を
    名乗っていた。読者は30日ずっと `// filepath:` に従って写しているので、そこに本物の
    パスがあれば、改善前のコードを本物のファイルへ貼る。しかもどれも閉じていない断片になる。

    見出しの判定はフェンスの外だけで行う。Bash のブロックは `# filepath: scripts/foo.sh`
    という行そのものが `#` 始まりなので、フェンスの中でも見出しとして数えると
    その行が in_sample を落とし、直後に自分自身を検査する前に対象から外れていた。
    """
    hits: list[tuple[int, str]] = []
    in_sample = False
    for i, line, state, _ in fence_states(text):
        if state == "outside":
            if line.startswith("#"):
                in_sample = ("Before" in line) or ("After" in line)
            continue
        if state != "inside" or not in_sample:
            continue
        fp = FILEPATH.match(line)
        if not fp:
            continue
        value = filepath_value(fp)
        if value.startswith(REAL_PREFIXES):
            hits.append((i, value))
    return hits


def find_missing(text: str, root: Path) -> list[tuple[int, str]]:
    """完成版に存在しないファイルを書き込み先として挙げている行を返す。

    実測で day30 の読み比べ用コードが、完成版に存在しない画面を名乗っていた。
    見出しに「例です」と書いても、コードを写す瞬間には視界に入らないので、
    読者はそのパスのファイルを作りにいく。

    root は完成版のルートを呼び出し側が明示する。値の末尾の `（…）` 注記は
    `app/(auth)` のようなルートグループと見分けがつく `_split_target` で剥がす。
    """
    from curriculum_blocks import _split_target

    hits: list[tuple[int, str]] = []
    for i, line, state, _ in fence_states(text):
        if state != "inside":
            continue
        fp = FILEPATH.match(line)
        if not fp:
            continue
        value, _ = _split_target(filepath_value(fp))
        if not value.startswith(REAL_PREFIXES):
            continue
        if not (root / value).exists():
            hits.append((i, value))
    return hits


def main(argv: list[str]) -> int:
    args: list[str] = []
    completed_root: Path | None = None
    it = iter(argv[1:])
    for a in it:
        if a == "--completed-root":
            completed_root = Path(next(it, ""))
        else:
            args.append(a)
    # 明示された完成版ルートがディレクトリとして存在しないなら、
    # 呼び出し側の指定ミス。対象の有無に関わらず先に止める
    # （対象0件で未判定に回ると、指定ミスが未判定に見えてしまう）。
    if completed_root is not None and not completed_root.is_dir():
        print(f"❌ 完成版ルートが見つかりません: {completed_root}", file=sys.stderr)
        return 2
    # 既定はリポジトリの curriculum/。cwd によらず動くようファイル位置から引く。
    default_dir = Path(__file__).resolve().parents[2] / "curriculum"
    args = args or [str(default_dir)]
    targets: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            targets.extend(sorted(p.glob("*.md")))
        elif p.is_file():
            targets.append(p)
        else:
            print(f"❌ 見つかりません: {a}", file=sys.stderr)
            return 2

    if not targets:
        # 走査対象が0件。検査を1件もしていないので緑にしない（D1 §8-3）。
        print("⏸️ 未判定: 走査対象が0件です（教材本文がまだ無い）")
        return NOT_JUDGED

    # 完成版ルートの既定はリポジトリの根。
    if completed_root is None:
        repo = Path(__file__).resolve().parents[2]
        if (repo / "app").is_dir() or (repo / "supabase").is_dir():
            completed_root = repo

    # 完成版がまだ1枚も無いルートを基準にしても実在確認はできない。
    # app/ も supabase/ も無いときは実在確認だけを未判定とする。
    can_judge = completed_root is not None and (
        (completed_root / "app").is_dir() or (completed_root / "supabase").is_dir()
    )

    findings: list[tuple[str, int, str]] = []
    missing: list[tuple[str, int, str]] = []
    samples: list[tuple[str, int, str]] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        for line, value in find(text):
            findings.append((path.name, line, value))
        if can_judge:
            for line, value in find_missing(text, completed_root):
                missing.append((path.name, line, value))
        for line, value in find_sample_with_real_path(text):
            samples.append((path.name, line, value))

    status = 0
    if findings:
        print(f"❌ 書き込み先が分からないコードブロック {len(findings)} 件")
        for name, line, value in findings:
            print(f"  {name}:{line} filepath: {value}")
        print("  実ファイル名を書くか、実ファイルを持たない旨を書いてください。")
        status = 1
    if missing:
        print(f"❌ 完成版に存在しないファイルを書き込み先にしている {len(missing)} 件")
        for name, line, value in missing:
            print(f"  {name}:{line} filepath: {value}")
        print("  読み比べ用なら、その旨をコード欄の中に書いてください。")
        status = 1
    if samples:
        print(f"❌ 読み比べ用の節が実ファイル名を名乗っている {len(samples)} 件")
        for name, line, value in samples:
            print(f"  {name}:{line} filepath: {value}")
        print("  読み比べ用サンプルである旨を書いてください。")
        status = 1
    if status:
        return status
    if not can_judge:
        print("⏸️ 未判定: 完成版ルート（app/ または supabase/）が無いため、"
              "書き込み先の実在確認は行っていません（--completed-root で明示できます）")
        return NOT_JUDGED

    print(f"✅ コードブロックの書き込み先 OK（{len(targets)} ファイル）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
