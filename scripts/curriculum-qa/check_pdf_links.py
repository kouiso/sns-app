#!/usr/bin/env python3
"""配布 PDF のリンク注釈が、読者の環境から開けない先を指していないかを見る。

旧 `check_zip_reference.py`（前作の販売ZIP版）のうち「配布物そのものの検査」を
引き継ぐ側。16 B9 / D23 で教材本文は **PDF が正本**になった。Vivliostyle で組んだ
PDF のリンク注釈は、作り手の環境を指す URI（`http://localhost:…` のプレビュー、
`file://` のローカルパス、スキーム無しの相対参照）をそのまま焼き込みうる。
買った人の環境ではどれも開けない。

終了コード:
  0 = PDF があり、リンク注釈を読めて、不正な指し先が無い
  1 = 読者の環境から開けない URI がある
  2 = 使い方の誤り・PDF として読めない
  3 = 未判定。PDF 成果物がまだ存在しない（Vivliostyle の組版は未着手）。
      「リンク0件の PASS」と「まだ判定できない」を分けるため PASS にはしない。
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

from sale_package import pdf_link_uris

NOT_JUDGED = 3

# 読者の手元で開けない URI の形。localhost 系・file:・相対参照は制作環境を指す。
BAD_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}
BAD_SCHEMES = {"file", "data", "javascript", "about", "chrome", "vivliostyle"}


def bad_uris(uris: frozenset[str]) -> list[str]:
    """読者の環境から開けない URI を返す。"""
    out: list[str] = []
    for u in sorted(uris):
        scheme = urlsplit(u).scheme.lower()
        host = urlsplit(u).hostname or ""
        if not scheme or scheme in BAD_SCHEMES or host.lower() in BAD_HOSTS:
            out.append(u)
    return out


def main(argv: list[str]) -> int:
    pdfs: list[Path] = []
    for a in argv[1:]:
        p = Path(a)
        if p.is_dir():
            pdfs.extend(sorted(p.glob("*.pdf")))
        elif p.is_file():
            pdfs.append(p)
        else:
            print(f"❌ 見つかりません: {a}", file=sys.stderr)
            return 2
    if not pdfs:
        # 組版成果物が無いことを「検査して問題なし」と書くと、
        # 配布物を見ていないゲートが緑に見える。未判定として報告する。
        print("⏸️ 未判定: 検査する PDF がまだありません（組版成果物が未生成）")
        return NOT_JUDGED

    status = 0
    for pdf in pdfs:
        try:
            uris = pdf_link_uris(pdf)
        except (ValueError, OSError) as e:
            print(f"❌ {e}", file=sys.stderr)
            return 2
        bad = bad_uris(uris)
        if bad:
            print(f"❌ {pdf.name}: 読者の環境から開けないリンク注釈 {len(bad)} 件")
            for u in bad:
                print(f"  {u}")
            print("  制作環境の URL が配布 PDF に残っています。公開URLへ直してください。")
            status = 1
        else:
            print(f"✅ {pdf.name}: リンク注釈 OK（{len(uris)} 件）")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
