#!/usr/bin/env python3
"""check_pdf_links.py の退行テスト。

止めるもの（制作環境を指す URI が配布 PDF に焼き込まれている）と、
止めてはいけないもの（公開 URL のリンク注釈）の両方を置く。
PDF がまだ無い間は「リンク0件の PASS」ではなく未判定（exit 3）を返す。
"""

import contextlib
import io
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_pdf_links import bad_uris  # noqa: E402
from check_pdf_links import main as check_main  # noqa: E402
from check_pdf_links import pdf_link_uris  # noqa: E402


def make_pdf(uris: list[str], *, compressed: bool = False) -> bytes:
    """リンク注釈を持つ最小限の PDF を返す。

    compressed=True のとき URI を FlateDecode ストリームの中にだけ置く。
    Vivliostyle 系の PDF は注釈をオブジェクトストリームへ圧縮して入れるので、
    表面の走査だけではこの URI は誰にも見えない。
    """
    literal = "".join(f"/URI ({u})\n" for u in uris).encode()
    if compressed:
        stream = zlib.compress(literal)
        return (
            b"%PDF-1.4\n1 0 obj\n<< /Length "
            + str(len(stream)).encode()
            + b" /Filter /FlateDecode >>\nstream\n"
            + stream
            + b"\nendstream\nendobj\n"
        )
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Annots [ << /Subtype /Link /A << /S /URI "
        + literal
        + b">> >> ] >>\nendobj\n"
    )


URI_CASES: list[tuple[str, frozenset[str], list[str]]] = [
    (
        "localhost を指すリンクは止める",
        frozenset({"http://localhost:8081/", "https://example.com/"}),
        ["http://localhost:8081/"],
    ),
    (
        "127.0.0.1 も制作環境なので止める",
        frozenset({"http://127.0.0.1:3000/preview"}),
        ["http://127.0.0.1:3000/preview"],
    ),
    (
        "file: スキームは読者の環境で開けない",
        frozenset({"file:///Users/me/dist/page.html"}),
        ["file:///Users/me/dist/page.html"],
    ),
    (
        "スキームの無い相対参照は止める",
        frozenset({"chapter-2.html"}),
        ["chapter-2.html"],
    ),
    (
        "公開 URL は通す",
        frozenset({"https://example.com/app", "https://github.com/kouiso/sns-app"}),
        [],
    ),
]


def check_exit_code() -> tuple[int, int]:
    def run(args: list[str]) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return check_main(args)

    failed = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)

        bad = root / "bad.pdf"
        bad.write_bytes(make_pdf(["http://localhost:8081/"]))
        if run(["check_pdf_links.py", str(bad)]) != 1:
            failed += 1
            print("  ❌ 制作環境の URI を含む PDF で 1 を返さない")

        # 圧縮ストリームの中の URI も見る。
        packed = root / "packed.pdf"
        packed.write_bytes(make_pdf(["file:///tmp/x"], compressed=True))
        if run(["check_pdf_links.py", str(packed)]) != 1:
            failed += 1
            print("  ❌ 圧縮ストリーム内の不正 URI で 1 を返さない")

        ok = root / "ok.pdf"
        ok.write_bytes(make_pdf(["https://example.com/"]))
        if run(["check_pdf_links.py", str(ok)]) != 0:
            failed += 1
            print("  ❌ 公開 URL だけの PDF で 0 を返さない")

        # PDF が1つも無いディレクトリは未判定（0件 PASS にしない）。
        (root / "empty").mkdir()
        if run(["check_pdf_links.py", str(root / "empty")]) != 3:
            failed += 1
            print("  ❌ PDF が無いディレクトリで 3（未判定）を返さない")

        if run(["check_pdf_links.py", "/no/such/path"]) != 2:
            failed += 1
            print("  ❌ 見つからないパスで 2 を返さない")

        not_pdf = root / "not.pdf"
        not_pdf.write_text("x", encoding="utf-8")
        if run(["check_pdf_links.py", str(not_pdf)]) != 2:
            failed += 1
            print("  ❌ PDF として読めないファイルで 2 を返さない")

        # /URI の16進文字列は2系統ある: BOM 付き UTF-16BE と、ASCII を
        # そのまま hex にしただけの物。後者を UTF-16BE で読むと化けて
        # localhost が見えなくなる。
        ascii_hex = b"http://localhost".hex().encode()
        hex_pdf = root / "hex-ascii.pdf"
        hex_pdf.write_bytes(
            b"%PDF-1.4\n1 0 obj\n<< /Annots [ << /Subtype /Link /A << /S /URI /URI <"
            + ascii_hex + b">> >> ] >>\nendobj\n"
        )
        # rc だけだと「化けた文字列もスキーム無しで止まる」ので通ってしまう。
        # 拾った URI そのものを比べる。
        if pdf_link_uris(hex_pdf) != frozenset({"http://localhost"}):
            failed += 1
            print("  ❌ ASCII hex の /URI を ASCII として読めていない")
        if run(["check_pdf_links.py", str(hex_pdf)]) != 1:
            failed += 1
            print("  ❌ ASCII hex の /URI で localhost を拾えない")

        be_hex = (b"\xfe\xff" + "http://localhost".encode("utf-16-be")).hex().encode()
        hex_be_pdf = root / "hex-be.pdf"
        hex_be_pdf.write_bytes(
            b"%PDF-1.4\n1 0 obj\n<< /Annots [ << /Subtype /Link /A << /S /URI /URI <"
            + be_hex + b">> >> ] >>\nendobj\n"
        )
        if pdf_link_uris(hex_be_pdf) != frozenset({"http://localhost"}):
            failed += 1
            print("  ❌ BOM 付き UTF-16BE の /URI を UTF-16BE として読めていない")
        if run(["check_pdf_links.py", str(hex_be_pdf)]) != 1:
            failed += 1
            print("  ❌ BOM 付き UTF-16BE の /URI で localhost を拾えない")
    return failed, 10


def main_test() -> int:
    failed = 0
    for name, uris, expected in URI_CASES:
        got = bad_uris(uris)
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    exit_failed, exit_total = check_exit_code()
    failed += exit_failed
    total = len(URI_CASES) + exit_total
    if failed:
        print(f"❌ check_pdf_links 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_pdf_links 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main_test())
