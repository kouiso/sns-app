#!/usr/bin/env python3
"""PDF / EPUB と章の開始状態を読む配布物プロバイダー。

このモジュールは成果物を生成しない。呼び出し側が明示した EPUB、PDF、または
スターターディレクトリだけを読み、検査に使える不変な一覧へ変換する。
"""

from __future__ import annotations

import re
import stat
import subprocess
import zipfile
from pathlib import Path

__all__ = [
    "comparable_source_paths",
    "epub_entries",
    "epub_source_paths",
    "links_from_pdftohtml",
    "pdf_link_targets",
    "starter_source_paths",
]

IGNORED_DIRS = frozenset({".expo", ".git", "dist", "node_modules"})
HREF = re.compile(r"\bhref=[\"']([^\"']+)[\"']", re.I)


def _validated_epub_infos(path: Path) -> tuple[tuple[zipfile.ZipInfo, str], ...]:
    """EPUBを検証し、ZipInfoと正規化したエントリ名を返す。"""
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError("EPUB が ZIP として壊れています") from exc
    with archive:
        infos = tuple(
            (info, info.filename.rstrip("/"))
            for info in archive.infolist()
            if info.filename.rstrip("/")
        )
        names = [name for _, name in infos]
        if len(names) != len(set(names)):
            raise ValueError("EPUB に重複するエントリ名があります")
        for name in names:
            if (
                "\\" in name
                or name.startswith("/")
                or any(part in {"", ".", ".."} for part in name.split("/"))
            ):
                raise ValueError(f"EPUB に安全でないエントリ名があります: {name}")
        try:
            media_type = archive.read("mimetype")
        except KeyError as exc:
            raise ValueError("EPUB に mimetype エントリがありません") from exc
        except (zipfile.BadZipFile, RuntimeError) as exc:
            raise ValueError("EPUB のエントリが壊れています") from exc
        if media_type != b"application/epub+zip":
            raise ValueError("mimetype が application/epub+zip ではありません")
        return infos


def epub_entries(path: Path) -> frozenset[str]:
    """正しい EPUB の全エントリ名を返す。"""
    return frozenset(name for _, name in _validated_epub_infos(path))


def epub_source_paths(path: Path) -> frozenset[str]:
    """EPUB に実ファイルとして同梱された照合可能なソースパスを返す。

    XHTML に印字された文字列、ディレクトリエントリ、Unix symlink はファイルの
    同梱を意味しないため数えない。この一覧が保証するのはパスの存在だけであり、
    参照元との内容一致や EPUB 全体の妥当性ではない。内容一致は
    ``comparable_source_paths`` の別契約で検査する。
    """
    return frozenset(
        name
        for info, name in _validated_epub_infos(path)
        if not info.is_dir()
        and not stat.S_ISLNK(info.external_attr >> 16)
        and (
            name in {"App.tsx", "package.json"}
            or name.startswith(("app/", "src/", "prisma/", "supabase/"))
        )
    )


def _source_tree_entries(root: Path) -> tuple[Path, ...]:
    """symlinkを含まない明示ルート配下のエントリを返す。"""
    if root.is_symlink():
        raise ValueError(f"ソースルートに symlink は使えません: {root}")
    if not root.is_dir():
        raise NotADirectoryError(root)
    entries = tuple(root.rglob("*"))
    for path in entries:
        if path.is_symlink():
            raise ValueError(f"ソースツリーに symlink は使えません: {path}")
    return entries


def starter_source_paths(root: Path) -> frozenset[str]:
    """明示された章スターターに最初から存在する通常ファイルを返す。

    ファイル・ディレクトリを問わず symlink は拒否し、ルート外を読み取らない。
    """
    return frozenset(
        path.relative_to(root).as_posix()
        for path in _source_tree_entries(root)
        if path.is_file()
        and not any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
    )


def comparable_source_paths(starter: Path, reference: Path) -> frozenset[str]:
    """symlinkの無い両ツリーで内容まで一致するファイルだけを返す。"""
    starter_paths = starter_source_paths(starter)
    _source_tree_entries(reference)
    return frozenset(
        rel
        for rel in starter_paths
        if (reference / rel).is_file()
        and (starter / rel).read_bytes() == (reference / rel).read_bytes()
    )


def links_from_pdftohtml(output: str) -> frozenset[str]:
    """pdftohtml の HTML 出力からリンク注釈の行き先を抽出する。"""
    return frozenset(match.group(1) for match in HREF.finditer(output))


def pdf_link_targets(path: Path, *, executable: str = "pdftohtml") -> frozenset[str]:
    """PDF のリンク注釈を pdftohtml で列挙する。"""
    if not path.is_file():
        raise FileNotFoundError(path)
    result = subprocess.run(
        [executable, "-stdout", "-i", "-noframes", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return links_from_pdftohtml(result.stdout)
