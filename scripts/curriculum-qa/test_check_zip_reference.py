#!/usr/bin/env python3
"""check_zip_reference.py の退行テスト。

止めるもの（配布EPUBに入らない `src/` と見比べさせる）と、止めてはいけないもの
（配布物に無い旨を添えてある／照合ではなく作成の指示／明示した同梱ファイルとの
照合／コードブロックの中）の両方を置く。
"""

import contextlib
import io
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_zip_reference import find_refs, main, not_in_distribution  # noqa: E402

AVAILABLE = frozenset(
    {
        "src/server/api/routers/_helpers/select.ts",
        "src/app/layout.tsx",
    }
)

CASES: list[tuple[str, str, list[int]]] = [
    (
        "配布EPUBに無い src/ との照合を指示したら止める",
        "完成形は、このリポジトリの `src/app/user/[id]/user-detail-client.tsx` と同じです。"
        "手元のコードと見比べてください。\n",
        [1],
    ),
    (
        "ZIP に入らない旨を添えてあれば通す",
        "見比べるときは、この1か所は違って当たり前だと思って読んでください。"
        "（販売用 ZIP に完成版の `src/` は入っていません）\n",
        [],
    ),
    (
        "現行のEPUBに無い旨を添えてあれば通す",
        "配布EPUBには完成版の `src/app/page.tsx` は含まれていません。"
        "そのため、見比べる必要はありません。\n",
        [],
    ),
    (
        "照合ではなく作成の指示は通す",
        "まず `src/app` の中に `dashboard` フォルダを作ります。\n",
        [],
    ),
    (
        "明示した同梱ファイルとの照合は通す",
        "`src/server/api/routers/_helpers/select.ts` を開き、教材のコードと見比べます。\n",
        [],
    ),
    (
        "prisma/ も ZIP に入らない",
        "`prisma/schema.prisma` と見比べて確認してください。\n",
        [1],
    ),
    (
        "コードブロックの中は対象外",
        "```bash\n# src/app/page.tsx と見比べてください\n```\n",
        [],
    ),
    (
        "src/ とだけ書いた文は置き場を指さない",
        "完成版の src/ と見比べる必要はありません。\n",
        [],
    ),
    (
        "折り返しで別の行に落ちても同じ段落なら止める",
        "完成形は、このリポジトリの `src/app/page.tsx` と\n見比べて確認してください。\n",
        [1],
    ),
    (
        "折り返しの断りも段落全体で読む",
        "`src/app/page.tsx` と\n見比べてください。\n"
        "（販売用 ZIP に完成版の `src/` は入っていません）\n",
        [],
    ),
    (
        "空行で切れていれば別の段落として扱う",
        "`src/app/error.tsx` を作ります。\n\n出来上がりを見比べて確認します。\n",
        [],
    ),
    (
        "隣り合う箇条書きは別の項目として扱う",
        "- `src/app/error.tsx` を作る\n- 出来上がりを見比べて確認する\n",
        [],
    ),
    (
        "表の行をまたいで同居させない",
        "| Step 1 | ファイルを作る | `src/app/error.tsx` |\n"
        "| Step 2 | 動きを見比べて確認する | - |\n",
        [],
    ),
    (
        "別の明示済み同梱ファイルとの照合は通す",
        "`src/app/layout.tsx` を開き、教材のコードと見比べます。\n",
        [],
    ),
    (
        "照合を打ち消している文は通す",
        "`src/app/page.tsx` と見比べる必要はありません。\n",
        [],
    ),
    (
        "打ち消しの言い回しが変わっても通す",
        "`src/app/page.tsx` と見比べないでください。\n"
        "`prisma/schema.prisma` と照合せずに進めます。\n"
        "`src/app/error.tsx` と比較して確認する必要ありません。\n",
        [],
    ),
    (
        "折り返しで打ち消しが次の行に落ちても通す",
        "完成形を `src/app/page.tsx` と見比べる\n必要はありません。\n",
        [],
    ),
    (
        "断りは、その断りが名指しした置き場にだけ効く",
        "`src/app/a.tsx` は ZIP には入っていません。"
        "一方、`src/app/b.tsx` と見比べて確認してください。\n",
        [1],
    ),
    (
        "断りと同じ文に在る置き場は通す",
        "完成版の `src/app/a.tsx` と見比べたくなりますが、ZIP には入っていません。\n",
        [],
    ),
    (
        "`./` 付きの置き場も判定に載せる",
        "完成形は `./src/app/page.tsx` と見比べて確認してください。\n",
        [1],
    ),
    (
        "先頭 `/` 付きの置き場も判定に載せる",
        "完成形は `/prisma/schema.prisma` と見比べて確認してください。\n",
        [1],
    ),
    (
        "リポジトリ名から書いた置き場も判定に載せる",
        "`task-app/package.json` と見比べて確認してください。\n",
        [1],
    ),
    (
        "前置き付きでも同梱ファイルなら通す",
        "`./src/server/api/routers/_helpers/select.ts` と見比べます。\n",
        [],
    ),
    (
        "コードブロックが段落を切る",
        "`src/app/page.tsx` を作ります。\n"
        "```bash\nnpm run dev\n```\n"
        "出来上がりを見比べて確認します。\n",
        [],
    ),
    (
        "打ち消しのない照合はこれまでどおり止める",
        "`src/app/page.tsx` と見比べる必要はありません。\n\n"
        "`src/app/error.tsx` と見比べて確認してください。\n",
        [3],
    ),
    (
        "照合先が別の文なら、作成の指示に出てくる置き場は挙げない",
        "`src/app/missing/page.tsx` を作ります。"
        "次に `README.md` と見比べて確認してください。\n",
        [],
    ),
    (
        "同じ段落に作成と照合が並んだら、照合の文の置き場だけ挙げる",
        "`src/app/a.tsx` を作ります。"
        "次に `src/app/b.tsx` と見比べて確認してください。\n",
        [1],
    ),
    (
        "同じ文に照合先が2つ並べば両方挙げる",
        "`src/app/a.tsx` と `src/app/b.tsx` を見比べて確認してください。\n",
        [1, 1],
    ),
    (
        "HTML コメントの中の照合指示は読者に見えない",
        "<!-- `src/app/page.tsx` と見比べて確認してください。 -->\n",
        [],
    ),
]


def check_exit_code() -> tuple[int, int]:
    def run(args: list[str]) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(args)

    failed = 0
    cases = [
        ("照合の指示が残っていれば 1 を返す", "`src/app/page.tsx` と見比べてください。\n", 1),
        ("問題が無ければ 0 を返す", "`src/app/page.tsx` を作ります。\n", 0),
    ]
    with tempfile.TemporaryDirectory() as d:
        epub = Path(d) / "book.epub"
        with zipfile.ZipFile(epub, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
        for name, body, want in cases:
            Path(d, "day05_x.md").write_text(body, encoding="utf-8")
            if run(["check_zip_reference.py", "--epub", str(epub), d]) != want:
                failed += 1
                print(f"  ❌ {name}")
        Path(d, "day05_x.md").write_text(
            "`app/screens.tsx` と見比べて確認してください。\n", encoding="utf-8"
        )
        directory_only = Path(d) / "directory-only.epub"
        with zipfile.ZipFile(directory_only, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("app/screens.tsx/", b"")
        if run(["check_zip_reference.py", "--epub", str(directory_only), d]) != 1:
            failed += 1
            print("  ❌ ディレクトリエントリを同梱ソースとして通した")
        actual_file = Path(d) / "actual-file.epub"
        with zipfile.ZipFile(actual_file, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("app/screens.tsx", b"export default null")
        if run(["check_zip_reference.py", "--epub", str(actual_file), d]) != 0:
            failed += 1
            print("  ❌ 実ファイルとして同梱された照合先を認識できない")
        if run(["check_zip_reference.py", "--epub", str(epub), "/no/such/path"]) != 2:
            failed += 1
            print("  ❌ 見つからない教材パスで 2 を返さない")
        empty = Path(d) / "empty"
        empty.mkdir()
        if run(["check_zip_reference.py", "--epub", str(epub), str(empty)]) != 2:
            failed += 1
            print("  ❌ 対象0件で 2 を返さない")
    if run(["check_zip_reference.py", "/no/such/path"]) != 2:
        failed += 1
        print("  ❌ EPUB 未指定で 2 を返さない")
    return failed, len(cases) + 5


def check_current_source_paths() -> tuple[int, int]:
    cases = [
        (
            "同梱されていないExpo Routerファイルを止める",
            "`app/screens.tsx` と見比べて確認してください。\n",
            frozenset(),
            [1],
        ),
        (
            "同梱されたExpo Routerファイルは通す",
            "`app/screens.tsx` と見比べて確認してください。\n",
            frozenset({"app/screens.tsx"}),
            [],
        ),
        (
            "同梱されていないSupabase migrationを止める",
            "`supabase/migrations/20261003_posts.sql` と照合してください。\n",
            frozenset(),
            [1],
        ),
        (
            "同梱されたSupabase migrationは通す",
            "`supabase/migrations/20261003_posts.sql` と照合してください。\n",
            frozenset({"supabase/migrations/20261003_posts.sql"}),
            [],
        ),
        (
            "同梱されていないルートApp.tsxを止める",
            "`App.tsx` と見比べて確認してください。\n",
            frozenset(),
            [1],
        ),
    ]
    failed = 0
    for name, body, available, expected in cases:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "day05_x.md"
            path.write_text(body, encoding="utf-8")
            got = [line for _, line, _, _ in find_refs([path], available)]
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")

    # PDF のリンク注釈はURLの存在しか示さず、ソース同梱の証拠にはならない。
    if not_in_distribution(
        "App.tsx", frozenset({"https://example.com/App.tsx"})
    ) is not True:
        failed += 1
        print("  ❌ PDFリンク注釈URLをソース同梱と誤認した")
    # basename が同じでも、異なる置き場のファイルは照合先にならない。
    if not_in_distribution("App.tsx", frozenset({"src/App.tsx"})) is not True:
        failed += 1
        print("  ❌ 異なる置き場の同名ソースを照合先と誤認した")
    return failed, len(cases) + 2


def main_test() -> int:
    failed = 0
    for name, body, expected in CASES:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "day05_x.md"
            p.write_text(body, encoding="utf-8")
            got = [i for _, i, _, _ in find_refs([p], AVAILABLE)]
        if sorted(got) != sorted(expected):
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    exit_failed, exit_total = check_exit_code()
    failed += exit_failed
    current_failed, current_total = check_current_source_paths()
    failed += current_failed
    total = len(CASES) + exit_total + current_total
    if failed:
        print(f"❌ check_zip_reference 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_zip_reference 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main_test())
