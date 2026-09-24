#!/usr/bin/env python3
"""check_epub_reference.py の退行テスト。

止めるもの（読者の手元に届かない物と見比べさせる指示）と、止めてはいけないもの
（配布物に入らない旨を添えてある／照合ではなく作成の指示／開始状態・EPUB・
公開リポジトリのどれかで届く置き場／コードブロックの中）の両方を置く。

「届くか」の判定は3系統（16 B9）に対して行う:
  - 開始状態（starter）
  - EPUB の同梱エントリ
  - 公開リポジトリに実在するファイル（repo_root）

`app/` `supabase/` `snapshots/` 配下の置き場は、完成版がまだ無い間は
「届かない」と断言できないので未判定（exit 3）側へ逃がす。
"""

import contextlib
import io
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_epub_reference import find_refs  # noqa: E402
from check_epub_reference import main as check_main  # noqa: E402

# (説明, 本文, starter, epub, 期待する違反行番号, 期待する未判定行番号)
CASES: list[tuple[str, str, frozenset[str], frozenset[str], list[int], list[int]]] = [
    (
        "完成版の置き場との照合は、完成版が無い間は未判定",
        "完成形は、このリポジトリの `app/user/[id]/x.tsx` と同じです。"
        "手元のコードと見比べてください。\n",
        frozenset(),
        frozenset(),
        [],
        [1],
    ),
    (
        "旧構成の src/ との照合指示は止める（現行構成に実体が無い）",
        "完成形は `src/app/page.tsx` と見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [1],
        [],
    ),
    (
        "配布物に入らない旨を添えてあれば通す",
        "見比べるときは、この1か所は違って当たり前だと思って読んでください。"
        "（完成版の `app/` は EPUB には入っていません）\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "照合ではなく作成の指示は通す",
        "まず `app` の中に `dashboard` フォルダを作ります。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "開始状態が配るファイルとの照合は通す",
        "`app/index.tsx` を開き、教材のコードと見比べます。\n",
        frozenset({"app/index.tsx"}),
        frozenset(),
        [],
        [],
    ),
    (
        "EPUB に同梱されるファイルとの照合は通す",
        "`OEBPS/listings/app-index.xhtml` と見比べて確認してください。\n",
        frozenset(),
        frozenset({"OEBPS/listings/app-index.xhtml"}),
        [],
        [],
    ),
    (
        "supabase/ も完成版が無い間は未判定",
        "`supabase/migrations/001_init.sql` と見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [],
        [1],
    ),
    (
        "コードブロックの中は対象外",
        "```bash\n# app/index.tsx と見比べてください\n```\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "app/ とだけ書いた文は置き場を指さない",
        "完成版の app/ と見比べる必要はありません。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "折り返しで別の行に落ちても同じ段落なら判定する",
        "完成形は、このリポジトリの `app/index.tsx` と\n見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [],
        [1],
    ),
    (
        "折り返しの断りも段落全体で読む",
        "`app/index.tsx` と\n見比べてください。\n"
        "（完成版の `app/` は EPUB には入っていません）\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "空行で切れていれば別の段落として扱う",
        "`app/error.tsx` を作ります。\n\n出来上がりを見比べて確認します。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "隣り合う箇条書きは別の項目として扱う",
        "- `app/error.tsx` を作る\n- 出来上がりを見比べて確認する\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "表の行をまたいで同居させない",
        "| Step 1 | ファイルを作る | `app/error.tsx` |\n"
        "| Step 2 | 動きを見比べて確認する | - |\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "照合を打ち消している文は通す",
        "`app/index.tsx` と見比べる必要はありません。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "打ち消しの言い回しが変わっても通す",
        "`app/index.tsx` と見比べないでください。\n"
        "`supabase/config.toml` と照合せずに進めます。\n"
        "`app/error.tsx` と比較して確認する必要ありません。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "折り返しで打ち消しが次の行に落ちても通す",
        "完成形を `app/index.tsx` と見比べる\n必要はありません。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "断りは、その断りが名指しした置き場にだけ効く",
        "`app/a.tsx` は EPUB には入っていません。"
        "一方、`src/legacy/b.tsx` と見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [1],
        [],
    ),
    (
        "断りと同じ文に在る置き場は通す",
        "完成版の `app/a.tsx` と見比べたくなりますが、EPUB には入っていません。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "`./` 付きの置き場も判定に載せる",
        "完成形は `./src/app/page.tsx` と見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [1],
        [],
    ),
    (
        "先頭 `/` 付きの置き場も判定に載せる",
        "完成形は `/prisma/schema.prisma` と見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [1],
        [],
    ),
    (
        "リポジトリ名から書いた置き場も判定に載せる",
        "`sns-app/package.json` と見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "前置き付きでも開始状態が配るファイルなら通す",
        "`./app/index.tsx` と見比べます。\n",
        frozenset({"app/index.tsx"}),
        frozenset(),
        [],
        [],
    ),
    (
        "コードブロックが段落を切る",
        "`app/index.tsx` を作ります。\n"
        "```bash\nnpm run dev\n```\n"
        "出来上がりを見比べて確認します。\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
    (
        "打ち消しのない照合はこれまでどおり止める",
        "`src/app/page.tsx` と見比べる必要はありません。\n\n"
        "`src/app/error.tsx` と見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [3],
        [],
    ),
    (
        "照合先が別の文なら、作成の指示に出てくる置き場は挙げない",
        "`app/missing/page.tsx` を作ります。"
        "次に `README.md` と見比べて確認してください。\n",
        frozenset({"README.md"}),
        frozenset(),
        [],
        [],
    ),
    (
        "同じ段落に作成と照合が並んだら、照合の文の置き場だけ挙げる",
        "`app/a.tsx` を作ります。"
        "次に `src/legacy/b.tsx` と見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [1],
        [],
    ),
    (
        "同じ文に照合先が2つ並べば両方挙げる",
        "`src/legacy/a.tsx` と `src/legacy/b.tsx` を見比べて確認してください。\n",
        frozenset(),
        frozenset(),
        [1, 1],
        [],
    ),
    (
        "HTML コメントの中の照合指示は読者に見えない",
        "<!-- `src/app/page.tsx` と見比べて確認してください。 -->\n",
        frozenset(),
        frozenset(),
        [],
        [],
    ),
]


def check_repo_root_reachable() -> int:
    """公開リポジトリ（repo_root）に実在するファイルとの照合は通す。

    完成版が書かれたあとの判定経路。repo_root 側に app/ が在れば、
    「届くか」は未判定ではなく実在確認で決まる。
    """
    failed = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "app").mkdir()
        (root / "app" / "index.tsx").write_text("x", encoding="utf-8")
        corpus = root / "chapters"
        corpus.mkdir()
        ok = corpus / "ch1.md"
        ok.write_text("`app/index.tsx` と見比べて確認してください。\n", encoding="utf-8")
        ng = corpus / "ch2.md"
        ng.write_text("`app/missing.tsx` と見比べて確認してください。\n", encoding="utf-8")
        hits, pending = find_refs([ok, ng], repo_root=root)
        if hits or pending:
            # hits は app/missing.tsx の1件だけのはず
            if [(n, i, loc) for n, i, loc, _ in hits] != [("ch2.md", 1, "app/missing.tsx")]:
                failed += 1
                print(f"  ❌ 完成版に無いパスを拾えていない: {hits}")
            if pending:
                failed += 1
                print(f"  ❌ 完成版があるのに未判定へ逃がした: {pending}")
    return failed


def check_exit_code() -> tuple[int, int]:
    def run(args: list[str]) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return check_main(args)

    failed = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        corpus = root / "chapters"
        corpus.mkdir()

        # 違反（src/ への照合指示）は 1。
        Path(corpus, "bad.md").write_text(
            "`src/app/page.tsx` と見比べてください。\n", encoding="utf-8"
        )
        if run(["check_epub_reference.py", str(corpus / "bad.md")]) != 1:
            failed += 1
            print("  ❌ 届かない照合先の指示で 1 を返さない")

        # app/ への照合指示は、完成版が無い間は 3（未判定）。
        Path(corpus, "pending.md").write_text(
            "`app/x.tsx` と見比べてください。\n", encoding="utf-8"
        )
        if run(["check_epub_reference.py", str(corpus / "pending.md"), "--repo-root", str(root)]) != 3:
            failed += 1
            print("  ❌ 完成版未作成の照合先で 3（未判定）を返さない")

        # 作成の指示だけなら 0。
        Path(corpus, "ok.md").write_text(
            "`app/x.tsx` を作ります。\n", encoding="utf-8"
        )
        if run(["check_epub_reference.py", str(corpus / "ok.md"), "--repo-root", str(root)]) != 0:
            failed += 1
            print("  ❌ 作成の指示だけの章で 0 を返さない")

        # --epub / --starter に存在しないパスを渡すと 2。
        if run(["check_epub_reference.py", str(corpus / "ok.md"), "--epub", str(root / "none.epub")]) != 2:
            failed += 1
            print("  ❌ 存在しない EPUB で 2 を返さない")
        if run(["check_epub_reference.py", str(corpus / "ok.md"), "--starter", str(root / "none")]) != 2:
            failed += 1
            print("  ❌ 存在しない開始状態で 2 を返さない")

    if run(["check_epub_reference.py", "/no/such/path"]) != 2:
        failed += 1
        print("  ❌ 見つからないパスで 2 を返さない")
    with tempfile.TemporaryDirectory() as d:
        if run(["check_epub_reference.py", d]) != 3:
            failed += 1
            print("  ❌ 対象0件で 3（未判定）を返さない")

    # 引数なしの既定走査でも curriculum/ が空なら未判定（D1 §8-3）。
    # REPO_ROOT を curriculum/ の無い一時ディレクトリへ差し替える。
    import check_epub_reference
    with tempfile.TemporaryDirectory() as d:
        saved = check_epub_reference.REPO_ROOT
        check_epub_reference.REPO_ROOT = Path(d)
        try:
            if run(["check_epub_reference.py"]) != 3:
                failed += 1
                print("  ❌ 既定対象0件で 3（未判定）を返さない")
        finally:
            check_epub_reference.REPO_ROOT = saved
    return failed, 8


def main_test() -> int:
    failed = 0
    for name, body, starter, epub, want_hits, want_pending in CASES:
        with tempfile.TemporaryDirectory() as d:
            # repo_root の tempdir には package.json だけを置く（実リポジトリの
            # 直下に在る置き場）。app/ supabase/ は置かないので、それらへの
            # 照合指示は未判定側へ回る。
            Path(d, "package.json").write_text("{}", encoding="utf-8")
            p = Path(d) / "ch_x.md"
            p.write_text(body, encoding="utf-8")
            hits, pending = find_refs([p], starter=starter, epub=epub, repo_root=Path(d))
        if sorted(i for _, i, _, _ in hits) != sorted(want_hits) or sorted(
            i for _, i, _ in pending
        ) != sorted(want_pending):
            failed += 1
            print(
                f"  ❌ {name}: 期待 hits={want_hits} pending={want_pending}"
                f" / 実際 hits={[i for _, i, _, _ in hits]} pending={[i for _, i, _ in pending]}"
            )
    failed += check_repo_root_reachable()
    exit_failed, exit_total = check_exit_code()
    failed += exit_failed
    total = len(CASES) + 1 + exit_total
    if failed:
        print(f"❌ check_epub_reference 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_epub_reference 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main_test())
