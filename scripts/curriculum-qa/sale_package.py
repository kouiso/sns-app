#!/usr/bin/env python3
"""読者の手元に届く物を、現在の配布形態から読み出す。

旧版は `scripts/build-zip.sh`（前作の ZIP 梱包）を読んで「ZIP に何が入るか」を
返していた。本作の配布は 16 B9 / D23 で **PDF が正本・EPUB を併産**と決まっており、
ZIP 梱包も scaffold スクリプトも存在しない。代わりにここが読むのは3系統
（`decisions/task-app資産棚卸し.md` の「配布は3系統」）:

  - 教材本文 …… PDF（正本）/ EPUB（併産）。EPUB は ZIP 形式なので、
    同梱ファイルの一覧は zipfile で読める。
  - 完成コード …… 公開リポジトリ（C3）。ここでは「リポジトリに実在するか」だけを見る。
  - 章末スナップショット / 開始状態 …… `snapshots/<章ID>/`（A7）や
    学習者の開始状態。どちらも現時点ではリポジトリに存在しないため、
    呼び出し側は「存在しなければ判定しない（未判定）」で扱う。

「手元に在るか」をこのモジュールが答え、「手元にある物と照合させる指示が
成り立つか」を判定するのは `check_epub_reference.py` の側である。
"""

from __future__ import annotations

import re
import zlib
from functools import cache
from pathlib import Path

__all__ = [
    "REPO_ROOT",
    "epub_entries",
    "pdf_link_uris",
    "starter_paths",
]

REPO_ROOT = Path(__file__).resolve().parents[2]


@cache
def epub_entries(epub: Path) -> frozenset[str]:
    """EPUB に同梱されるファイルのパス一覧。EPUB は ZIP 形式（16 B9 / D23）。

    返すのはエントリ名そのまま（`OEBPS/xxx.xhtml` など）。教材本文が
    「EPUB に入っているファイル」と見なせるかの判定は呼び出し側が行う。
    """
    import zipfile

    if not zipfile.is_zipfile(epub):
        raise ValueError(f"EPUB（ZIP形式）として読めません: {epub}")
    with zipfile.ZipFile(epub) as zf:
        return frozenset(zf.namelist())


def _literal_string(raw: bytes) -> bytes:
    """PDF の `( )` 文字列の逃がし記号と8進を戻す。"""
    esc = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
           b"(": b"(", b")": b")", b"\\": b"\\"}
    out, i = [], 0
    while i < len(raw):
        ch = raw[i:i + 1]
        if ch != b"\\":
            out.append(ch)
            i += 1
            continue
        nxt = raw[i + 1:i + 2]
        if nxt in esc:
            out.append(esc[nxt])
            i += 2
        elif nxt in (b"\n", b"\r"):
            i += 2
        elif nxt in b"01234567":
            m = re.match(rb"[0-7]{1,3}", raw[i + 1:])
            out.append(bytes([int(m.group(0), 8) & 0xFF]))
            i += 1 + len(m.group(0))
        else:
            i += 1
    return b"".join(out)


def _pdf_bodies(data: bytes) -> list[bytes]:
    """全オブジェクトの中身を返す。FlateDecode のストリームは展開した中身も添える。

    Vivliostyle などが出す PDF ではリンク注釈（/Annots /Subtype /Link の
    /A << /S /URI /URI (...) >>）がオブジェクトストリームの中に圧縮されて
    入っていることがある。表面だけ走査するとその注釈は誰にも見えないまま
    通ってしまうので、展開できるストリームはすべて覗く。
    展開できないストリームがあると、そこにだけ在るリンクは検査から抜ける。
    黙って続けると「リンクは確認済み」の嘘になるので、失敗したら止める。
    """
    hdr = re.compile(rb"(?:^|[\s>])(\d+)\s+(\d+)\s+obj\b")
    bodies: list[bytes] = []
    pos = 0
    while True:
        m = hdr.search(data, pos)
        if not m:
            return bodies
        start = m.end()
        end = data.find(b"endobj", start)
        if end == -1:
            end = len(data)
        body = data[start:end]
        bodies.append(body)
        sm = re.search(rb"stream\r?\n", body)
        if sm and b"FlateDecode" in body[: sm.start()]:
            head_end = sm.start()
            lm = re.search(rb"/Length\s+(\d+)", body[:head_end])
            raw = None
            if lm:
                n = int(lm.group(1))
                cand = body[sm.end(): sm.end() + n]
                if b"endstream" in body[sm.end() + n: sm.end() + n + 32]:
                    raw = cand
            if raw is None:
                es = body.find(b"endstream", sm.end())
                if es != -1:
                    raw = body[sm.end():es]
            if raw is not None:
                try:
                    bodies.append(zlib.decompress(raw))
                except zlib.error as e:
                    raise ValueError(f"PDF のストリーム展開に失敗しました（{e}）")
        pos = end + 6


@cache
def pdf_link_uris(pdf: Path) -> frozenset[str]:
    """PDF のリンク注釈が指す URI の集合。

    「紙面に印刷されるリンク」を確認するために、本文の見た目ではなく
    /Annots の /URI を読む。取り出せるのは URI アクションだけであり、
    ページ内リンク（/Dest）やリンクの無い文字列は対象外。
    """
    data = pdf.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError(f"PDF として読めません: {pdf}")
    uris: set[str] = set()
    for body in _pdf_bodies(data):
        for m in re.finditer(rb"/URI\s*\(((?:[^()\\]|\\[\s\S])*)\)", body):
            uris.add(_literal_string(m.group(1)).decode("utf-8", "replace"))
        for m in re.finditer(rb"/URI\s*<([0-9A-Fa-f\s]+)>", body):
            h = re.sub(rb"\s", b"", m.group(1)).decode()
            if len(h) % 2:
                h += "0"
            uris.add(bytes.fromhex(h).decode("utf-16-be", "replace"))
    return frozenset(uris)


# EPUB・PDF は不変の成果物なので読み出しをキャッシュしてよいが、
# 開始状態は編集中に変わるディレクトリなのでキャッシュしない。
def starter_paths(starter: Path) -> frozenset[str]:
    """学習者の開始状態（スターター）が配るファイルの相対パス一覧。

    2つの形を受ける:
      - ディレクトリ …… 配布するファイルツリーそのもの（相対パスで返す）
      - ファイル     …… 1行1パスの一覧表。空行と `#` 始まりの行は注釈。
    開始状態は現時点でリポジトリに存在しない（10 §3 G0 の未決項）。
    この関数は「在れば読む」だけを担い、不在の扱いは呼び出し側が決める。
    """
    if starter.is_dir():
        return frozenset(
            f.relative_to(starter).as_posix()
            for f in sorted(starter.rglob("*"))
            if f.is_file()
        )
    if starter.is_file():
        return frozenset(
            line.strip()
            for line in starter.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    raise ValueError(f"開始状態（ディレクトリまたは一覧ファイル）ではありません: {starter}")
