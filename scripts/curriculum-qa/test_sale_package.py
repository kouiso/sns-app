#!/usr/bin/env python3
"""PDF / EPUB / 章スターターの配布物プロバイダー退行テスト。"""

from __future__ import annotations

import sys
import tempfile
import warnings
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sale_package import (  # noqa: E402
    comparable_source_paths,
    epub_entries,
    epub_source_paths,
    links_from_pdftohtml,
    starter_source_paths,
)


def make_epub(
    path: Path,
    entries: dict[str, bytes],
    *,
    media_type: bytes = b"application/epub+zip",
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", media_type)
        for name, body in entries.items():
            archive.writestr(name, body)


def main_test() -> int:
    failed = 0
    total = 0

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        epub = root / "book.epub"
        make_epub(
            epub,
            {
                "EPUB/chapter.xhtml": b"<html/>",
                "App.tsx": b"root app",
                "app/screens.tsx": b"router screen",
                "src/App.tsx": b"export default 1",
                "supabase/migrations/20261003_posts.sql": b"create table posts();",
                "examples/App.tsx": b"same basename, different location",
                "package.json": b"{}",
            },
        )
        entries = epub_entries(epub)
        total += 2
        if "EPUB/chapter.xhtml" not in entries:
            failed += 1
            print("  ❌ EPUB の本文エントリを列挙できない")
        if epub_source_paths(epub) != frozenset(
            {
                "App.tsx",
                "app/screens.tsx",
                "src/App.tsx",
                "supabase/migrations/20261003_posts.sql",
                "package.json",
            }
        ):
            failed += 1
            print("  ❌ XHTML・同名別パスと同梱ソースを区別できない")

        spoofed = root / "spoofed.epub"
        symlink = zipfile.ZipInfo("src/App.tsx")
        symlink.create_system = 3
        symlink.external_attr = (0o120777 << 16)
        with zipfile.ZipFile(spoofed, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("app/screens.tsx/", b"")
            archive.writestr(symlink, b"../real/App.tsx")
        total += 2
        spoofed_entries = epub_entries(spoofed)
        if not {"app/screens.tsx", "src/App.tsx"}.issubset(spoofed_entries):
            failed += 1
            print("  ❌ EPUB の全エントリ安全検査から特殊エントリが消えた")
        if epub_source_paths(spoofed):
            failed += 1
            print("  ❌ ディレクトリまたはsymlinkを同梱ソースと誤認した")

        bad = root / "bad.epub"
        make_epub(bad, {}, media_type=b"application/zip")
        total += 1
        try:
            epub_entries(bad)
        except ValueError:
            pass
        else:
            failed += 1
            print("  ❌ EPUB でない ZIP を受理した")

        corrupt = root / "corrupt.epub"
        corrupt.write_bytes(b"not a zip")
        total += 1
        try:
            epub_entries(corrupt)
        except ValueError:
            pass
        else:
            failed += 1
            print("  ❌ 壊れたEPUBを受理した")

        unsafe_names = ["../src/App.tsx", "https://example.com/App.tsx"]
        for index, unsafe_name in enumerate(unsafe_names):
            unsafe = root / f"unsafe-{index}.epub"
            make_epub(unsafe, {unsafe_name: b"bad"})
            total += 1
            try:
                epub_entries(unsafe)
            except ValueError:
                pass
            else:
                failed += 1
                print(f"  ❌ 安全でないEPUBエントリを受理した: {unsafe_name}")

        duplicate = root / "duplicate.epub"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("mimetype", "application/epub+zip")
                archive.writestr("src/App.tsx", "first")
                archive.writestr("src/App.tsx", "second")
        total += 1
        try:
            epub_entries(duplicate)
        except ValueError:
            pass
        else:
            failed += 1
            print("  ❌ 重複するEPUBソースエントリを受理した")

        starter = root / "starter"
        reference = root / "reference"
        (starter / "src").mkdir(parents=True)
        (starter / "node_modules/pkg").mkdir(parents=True)
        (reference / "src").mkdir(parents=True)
        (starter / "src/App.tsx").write_text("same", encoding="utf-8")
        (starter / "src/OnlyStarter.ts").write_text("starter", encoding="utf-8")
        (starter / "node_modules/pkg/index.js").write_text("generated", encoding="utf-8")
        (reference / "src/App.tsx").write_text("same", encoding="utf-8")
        (reference / "src/OnlyStarter.ts").write_text("different", encoding="utf-8")
        total += 3
        paths = starter_source_paths(starter)
        if "src/App.tsx" not in paths or "src/OnlyStarter.ts" not in paths:
            failed += 1
            print("  ❌ スターターの実ファイルを列挙できない")
        if any(path.startswith("node_modules/") for path in paths):
            failed += 1
            print("  ❌ 再取得可能な依存をスターターとして数えた")
        if comparable_source_paths(starter, reference) != frozenset({"src/App.tsx"}):
            failed += 1
            print("  ❌ 内容が違うファイルを照合可能と判定した")

        outside_file = root / "outside-secret.txt"
        outside_file.write_text("secret", encoding="utf-8")
        outside_dir = root / "outside-dir"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_text("secret", encoding="utf-8")

        symlink_cases: list[tuple[str, Path, object]] = []
        starter_file_link = root / "starter-file-link"
        (starter_file_link / "src").mkdir(parents=True)
        (starter_file_link / "src/Secret.ts").symlink_to(outside_file)
        symlink_cases.append(
            ("スターターの外部ファイルsymlink", starter_file_link, starter_file_link)
        )

        reference_file_link = root / "reference-file-link"
        (reference_file_link / "src").mkdir(parents=True)
        (reference_file_link / "src/App.tsx").symlink_to(outside_file)
        symlink_cases.append(
            ("参照元の外部ファイルsymlink", reference_file_link, (starter, reference_file_link))
        )

        starter_dir_link = root / "starter-dir-link"
        starter_dir_link.mkdir()
        (starter_dir_link / "external").symlink_to(outside_dir, target_is_directory=True)
        symlink_cases.append(
            ("スターターの外部directory symlink", starter_dir_link, starter_dir_link)
        )

        reference_dir_link = root / "reference-dir-link"
        reference_dir_link.mkdir()
        (reference_dir_link / "external").symlink_to(outside_dir, target_is_directory=True)
        symlink_cases.append(
            ("参照元の外部directory symlink", reference_dir_link, (starter, reference_dir_link))
        )

        total += len(symlink_cases)
        for label, _, call_args in symlink_cases:
            try:
                if isinstance(call_args, tuple):
                    comparable_source_paths(*call_args)
                else:
                    starter_source_paths(call_args)
            except ValueError:
                pass
            else:
                failed += 1
                print(f"  ❌ {label} を拒否しなかった")

    total += 2
    links = links_from_pdftohtml(
        '<a href="https://example.com/a">a</a><a href="#p2">b</a>'
    )
    if links != frozenset({"https://example.com/a", "#p2"}):
        failed += 1
        print("  ❌ PDFリンク注釈の行き先を抽出できない")
    if links_from_pdftohtml("<p>https://example.com/plain</p>"):
        failed += 1
        print("  ❌ リンク注釈でない印字文字列をリンクとして数えた")

    if failed:
        print(f"❌ sale_package 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ sale_package 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main_test())
