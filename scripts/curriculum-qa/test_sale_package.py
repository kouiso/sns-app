#!/usr/bin/env python3
"""sale_package.py の退行テスト。

見張るのは「読者の手元に届く物」の読み出し側。前作は build-zip.sh と
scaffold-from-scratch.sh の2本から配布物を再構成していたが、本作の配布は
PDF 正本・EPUB 併産・公開リポジトリ・開始状態の4系統（16 B9 / D23 /
task-app資産棚卸し §4）で、ZIP 梱包も scaffold スクリプトも存在しない。

ここで止めるのは3点:

  - EPUB / PDF / 開始状態の読み出しが、実物に対して正しく答えること
  - 実物が無い・読めないときに ValueError になること
    （不在を空の一覧で返すと、呼び出し側が「違反なし」と「未判定」を
    見分けられなくなる。D14-8 の「検査件数0は緑にしない」に倣う）
  - 畳んだ返り値を呼び出し側が書き換えられないこと（frozenset）
"""

import sys
import tempfile
import warnings
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sale_package import (  # noqa: E402
    comparable_source_paths,
    epub_entries,
    epub_source_paths,
    links_from_pdftohtml,
    pdf_link_uris,
    starter_source_paths,
    starter_paths,
)


def make_epub(path: Path, entries: list[str]) -> None:
    """最小限の EPUB（ZIP）を作る。mimetype は先頭に無圧縮で置く決まり。"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name in entries:
            zf.writestr(name, "x")


def make_pdf(path: Path, uris: list[str]) -> bytes:
    """リンク注釈を持つ最小限の PDF を作る。圧縮ストリームの中にも置く。"""
    literal = "".join(f"/URI ({u})\n" for u in uris)
    inner = literal.encode()
    stream = zlib.compress(inner)
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Annots [ << /Subtype /Link /A << /S /URI "
        + literal.encode()
        + b">> >> ] >>\nendobj\n"
        + b"2 0 obj\n<< /Length "
        + str(len(stream)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + stream
        + b"\nendstream\nendobj\n"
    )


def check_epub() -> tuple[int, int]:
    failed = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        epub = root / "book.epub"
        make_epub(epub, ["OEBPS/content.xhtml", "OEBPS/style.css"])
        got = epub_entries(epub)
        if got != frozenset({"mimetype", "OEBPS/content.xhtml", "OEBPS/style.css"}):
            failed += 1
            print(f"  ❌ EPUB の同梱一覧が取れない: {sorted(got)}")
        if not isinstance(got, frozenset):
            failed += 1
            print("  ❌ epub_entries が書き換えられる型を返している")
        if epub_entries(epub) is not got:
            failed += 1
            print("  ❌ epub_entries が呼ぶたびに読み直している")

        for name, bad in (
            ("存在しない EPUB", root / "none.epub"),
            ("ZIP ではないファイル", root / "not.zip"),
            ("ディレクトリ", root),
        ):
            if name == "ZIP ではないファイル":
                bad.write_text("x", encoding="utf-8")
            try:
                epub_entries(bad)
            except (ValueError, OSError):
                pass
            else:
                failed += 1
                print(f"  ❌ {name}を ValueError なしで通した")
    return failed, 6


def check_pdf() -> tuple[int, int]:
    failed = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        pdf = root / "book.pdf"
        pdf.write_bytes(make_pdf(pdf, ["https://example.com/a", "https://example.com/b"]))
        got = pdf_link_uris(pdf)
        if "https://example.com/a" not in got or "https://example.com/b" not in got:
            failed += 1
            print(f"  ❌ PDF のリンク URI が取れない: {sorted(got)}")
        if not isinstance(got, frozenset):
            failed += 1
            print("  ❌ pdf_link_uris が書き換えられる型を返している")
        if pdf_link_uris(pdf) is not got:
            failed += 1
            print("  ❌ pdf_link_uris が呼ぶたびに読み直している")

        # 16 B9 の危惧どおり、注釈が圧縮ストリームの中にあっても拾えること。
        # make_pdf は同じ URI をストリームの中にも入れている。
        for name, bad in (
            ("存在しない PDF", root / "none.pdf"),
            ("PDF ではないファイル", root / "not.pdf"),
            ("ディレクトリ", root),
        ):
            if name == "PDF ではないファイル":
                bad.write_text("x", encoding="utf-8")
            try:
                pdf_link_uris(bad)
            except (ValueError, OSError):
                pass
            else:
                failed += 1
                print(f"  ❌ {name}を ValueError なしで通した")
    return failed, 6


def check_starter() -> tuple[int, int]:
    failed = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)

        # ディレクトリ形: ツリーをそのまま相対パスで返す。
        tree = root / "starter"
        (tree / "app").mkdir(parents=True)
        (tree / "app" / "index.tsx").write_text("x", encoding="utf-8")
        (tree / "package.json").write_text("{}", encoding="utf-8")
        got = starter_paths(tree)
        if got != frozenset({"app/index.tsx", "package.json"}):
            failed += 1
            print(f"  ❌ 開始状態ツリーの一覧が取れない: {sorted(got)}")

        # 一覧ファイル形: 1行1パス。空行と # 注釈は読み飛ばす。
        manifest = root / "starter.txt"
        manifest.write_text(
            "# 開始状態\napp/index.tsx\n\npackage.json\n", encoding="utf-8"
        )
        got = starter_paths(manifest)
        if got != frozenset({"app/index.tsx", "package.json"}):
            failed += 1
            print(f"  ❌ 開始状態一覧ファイルが読めない: {sorted(got)}")

        try:
            starter_paths(root / "none")
        except (ValueError, OSError):
            pass
        else:
            failed += 1
            print("  ❌ 存在しない開始状態を ValueError なしで通した")

        if not isinstance(starter_paths(tree), frozenset):
            failed += 1
            print("  ❌ starter_paths が書き換えられる型を返している")
        # 開始状態は編集中に変わるディレクトリなのでキャッシュしない。
        # 呼ぶたびに最新の中身を返すことをここで確認する。
        (tree / "extra.txt").write_text("x", encoding="utf-8")
        if "extra.txt" not in starter_paths(tree):
            failed += 1
            print("  ❌ starter_paths が古い一覧を返している")
    return failed, 5


def check_strict_sources() -> tuple[int, int]:
    """実ファイル照合とfilesystem escape防止の追加契約を検証する。"""
    failed = 0
    total = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        epub = root / "sources.epub"
        with zipfile.ZipFile(epub, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("App.tsx", "root")
            archive.writestr("app/screens.tsx", "screen")
            archive.writestr("supabase/migrations/posts.sql", "sql")
            archive.writestr("examples/App.tsx", "other")
        total += 1
        if epub_source_paths(epub) != frozenset(
            {"App.tsx", "app/screens.tsx", "supabase/migrations/posts.sql"}
        ):
            failed += 1
            print("  ❌ EPUBの同梱ソースパスを正確に絞れない")

        spoofed = root / "spoofed.epub"
        link = zipfile.ZipInfo("src/App.tsx")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        with zipfile.ZipFile(spoofed, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("app/screens.tsx/", b"")
            archive.writestr(link, b"../real/App.tsx")
        total += 1
        if epub_source_paths(spoofed):
            failed += 1
            print("  ❌ EPUBのdirectoryまたはsymlinkを実ソースと誤認した")

        unsafe = root / "unsafe.epub"
        with zipfile.ZipFile(unsafe, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("../src/App.tsx", "bad")
        total += 1
        try:
            epub_entries(unsafe)
        except ValueError:
            pass
        else:
            failed += 1
            print("  ❌ EPUBのtraversal entryを拒否しなかった")

        duplicate = root / "duplicate.epub"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("mimetype", "application/epub+zip")
                archive.writestr("src/App.tsx", "one")
                archive.writestr("src/App.tsx", "two")
        total += 1
        try:
            epub_entries(duplicate)
        except ValueError:
            pass
        else:
            failed += 1
            print("  ❌ EPUBの重複entryを拒否しなかった")

        starter = root / "starter-source"
        reference = root / "reference"
        (starter / "src").mkdir(parents=True)
        (reference / "src").mkdir(parents=True)
        (starter / "src/App.tsx").write_text("same", encoding="utf-8")
        (reference / "src/App.tsx").write_text("same", encoding="utf-8")
        total += 1
        if comparable_source_paths(starter, reference) != frozenset({"src/App.tsx"}):
            failed += 1
            print("  ❌ 内容が一致する通常ファイルを照合できない")

        outside_file = root / "secret.txt"
        outside_file.write_text("secret", encoding="utf-8")
        outside_dir = root / "secret-dir"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_text("secret", encoding="utf-8")
        bad_roots: list[tuple[str, Path, Path | None]] = []
        for side, target, is_directory in (
            ("starter-file", outside_file, False),
            ("starter-dir", outside_dir, True),
        ):
            tree = root / side
            tree.mkdir()
            (tree / "escape").symlink_to(target, target_is_directory=is_directory)
            bad_roots.append((side, tree, None))
        for side, target, is_directory in (
            ("reference-file", outside_file, False),
            ("reference-dir", outside_dir, True),
        ):
            tree = root / side
            tree.mkdir()
            (tree / "escape").symlink_to(target, target_is_directory=is_directory)
            bad_roots.append((side, starter, tree))
        total += len(bad_roots)
        for label, first, second in bad_roots:
            try:
                if second is None:
                    starter_source_paths(first)
                else:
                    comparable_source_paths(first, second)
            except ValueError:
                pass
            else:
                failed += 1
                print(f"  ❌ {label} symlinkを拒否しなかった")

    total += 2
    if links_from_pdftohtml('<a href="https://example.com">x</a>') != frozenset(
        {"https://example.com"}
    ):
        failed += 1
        print("  ❌ pdftohtmlのlink annotationを抽出できない")
    if links_from_pdftohtml("<p>https://example.com</p>"):
        failed += 1
        print("  ❌ PDFの印字URLをlink annotationと誤認した")
    return failed, total


def main_test() -> int:
    failed = 0
    epub_failed, epub_total = check_epub()
    failed += epub_failed
    pdf_failed, pdf_total = check_pdf()
    failed += pdf_failed
    starter_failed, starter_total = check_starter()
    failed += starter_failed
    strict_failed, strict_total = check_strict_sources()
    failed += strict_failed
    total = epub_total + pdf_total + starter_total + strict_total
    if failed:
        print(f"❌ sale_package 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ sale_package 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main_test())
