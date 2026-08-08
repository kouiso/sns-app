"""PDF の本文を標準ライブラリだけで取り出す。

使い方:  python3 extract_pdf_text.py <PDFのパス>

`17_文体正本の実測.md` の数値は、このスクリプトを
`変数と定数 _ver.1.0.0.pdf` に対して実行した結果から数えた。
PDF 本体は局長の著作物なのでリポジトリには入れていない。
"""
import re, zlib, sys, unicodedata

USAGE = "使い方: python3 extract_pdf_text.py <PDFのパス> [--text]"
if not 2 <= len(sys.argv) <= 3:
    sys.exit(USAGE)
# 綴り違いを黙って無視すると、本文が出ないのを仕様だと思い込む。
if len(sys.argv) == 3 and sys.argv[2] != "--text":
    sys.exit(f"知らない指定です: {sys.argv[2]}\n{USAGE}")
data = open(sys.argv[1], "rb").read()

# --- collect all objects ---
objs = {}
for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", data, re.S):
    objs[int(m.group(1))] = m.group(3)

def stream_of(body, num=None):
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    start = m.end()
    end = body.find(b"endstream", start)
    raw = body[start:end]
    if b"FlateDecode" in body[:m.start()]:
        # 途中まで展開できてもそれは本文の欠けた状態なので、採用せず止める。
        # 欠けたまま数えると、実測値が黙って小さく出る。
        try:
            return zlib.decompress(raw)
        except Exception as e:
            raise SystemExit(f"オブジェクト {num} の展開に失敗しました（{e}）。実測を中止します。")
    return raw

# --- build ToUnicode CMaps per font ---
cmaps = {}  # objnum of tounicode -> dict
for num, body in objs.items():
    s = stream_of(body, num)
    if not s or (b"beginbfchar" not in s and b"beginbfrange" not in s):
        continue
    mp = {}
    for blk in re.findall(rb"beginbfchar(.*?)endbfchar", s, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            src = int(a, 16)
            dst = bytes.fromhex(b.decode()).decode("utf-16-be", "ignore")
            mp[src] = dst
    for blk in re.findall(rb"beginbfrange(.*?)endbfrange", s, re.S):
        for a, b, c in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            lo, hi, st = int(a, 16), int(b, 16), int(c, 16)
            for i in range(lo, min(hi, lo + 65535) + 1):
                mp[i] = chr(st + (i - lo))
    cmaps[num] = mp

# map font resource name -> cmap, per page-ish: build global font->cmap
font_to_cmap = {}
for num, body in objs.items():
    if b"/Type" in body and b"/Font" in body:
        m = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", body)
        if m and int(m.group(1)) in cmaps:
            font_to_cmap[num] = cmaps[int(m.group(1))]

# page resources: /F1 12 0 R
def page_fontmap(body):
    out = {}
    for name, n in re.findall(rb"/([A-Za-z0-9#\.\-\+]+)\s+(\d+)\s+0\s+R", body):
        n = int(n)
        if n in font_to_cmap:
            out[name.decode()] = font_to_cmap[n]
    return out

# --- pages ---
pages = []
for num, body in objs.items():
    if re.search(rb"/Type\s*/Page[^s]", body):
        pages.append((num, body))

def resolve_res(body):
    # /Resources が別オブジェクトなら引く。ページ本体に直接書いてあるなら本体を返す。
    m = re.search(rb"/Resources\s+(\d+)\s+0\s+R", body)
    if m:
        return objs.get(int(m.group(1)), b"")
    return body

def unify(c):
    """このPDFの対応表は「貝」「一」など33種の漢字を、字形の同じ康熙部首
    （U+2F00〜U+2FDF）で返してくる。見た目は同じだが別の文字なので、
    検索も比較もできない。通常の漢字へ戻す。"""
    if 0x2F00 <= ord(c) <= 0x2FDF:
        return unicodedata.normalize("NFKC", c)
    return c


def decode_hex(h, cmap):
    s = h.decode()
    res = []
    for i in range(0, len(s), 4):
        code = int(s[i:i+4], 16)
        if cmap and code in cmap:
            res.append("".join(map(unify, cmap[code])))
        else:
            res.append("�")
    return "".join(res)

texts = []
for num, body in sorted(pages):
    res = resolve_res(body)
    fm = page_fontmap(res + body)
    content = b""
    for m in re.finditer(rb"/Contents\s+(\d+)\s+0\s+R", body):
        cnum = int(m.group(1))
        c = objs.get(cnum)
        if c:
            s = stream_of(c, cnum)
            if s:
                content += s
    if not content:
        continue
    cur = None
    out = []
    for tok in re.finditer(rb"/([A-Za-z0-9#\.\-\+]+)\s+[\d\.]+\s+Tf|<([0-9A-Fa-f]+)>\s*Tj|\[(.*?)\]\s*TJ|\(((?:\\.|[^()\\])*)\)\s*Tj|(TD|Td|T\*|ET)", content, re.S):
        if tok.group(1):
            cur = fm.get(tok.group(1).decode())
        elif tok.group(2):
            h = tok.group(2)
            out.append(decode_hex(h, cur))
        elif tok.group(3):
            for hm in re.finditer(rb"<([0-9A-Fa-f]+)>", tok.group(3)):
                out.append(decode_hex(hm.group(1), cur))
        elif tok.group(4) is not None:
            out.append(tok.group(4).decode("latin-1"))
        elif tok.group(5):
            out.append("\n")
    texts.append((num, "".join(out)))


# --- 発話に切り分けて数える -----------------------------------------------
LABELS = ("磯貝）", "阿部）")


def split_turns(flat):
    parts = re.split("(" + "|".join(map(re.escape, LABELS)) + ")", flat)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]


def headings(first_page):
    """1ページ目は目次。ブロックごとに切って見出し候補にする。"""
    cands = [re.sub(r"\s", "", b) for b in re.split(r"\n\s*\n", first_page)]
    return [h for h in cands if 1 < len(h) < 40]


def strip_trailing(text, heads):
    """発話の末尾に貼り付いた節見出しを外す。"""
    changed = True
    while changed:
        changed = False
        for h in heads:
            if text.endswith(h) and len(text) > len(h):
                text = text[: -len(h)]
                changed = True
    return text


# 抽出に失敗したPDFを渡されたとき、全部0の「実測」を印字すると
# 本物の測定値と見分けがつかない。数える前に止める。
if not texts:
    sys.exit("本文のあるページが1枚も取れませんでした。実測を中止します。")

page_texts = [t for _, t in texts]
flat = re.sub(r"\s", "", "".join(page_texts))
turns = split_turns(flat)
if not turns:
    sys.exit("「磯貝）」「阿部）」の話者ラベルが1件も見つかりません。実測を中止します。")
heads = headings(page_texts[0]) if page_texts else []

teacher = [x for lbl, x in turns if lbl.startswith("磯")]
student = [x for lbl, x in turns if lbl.startswith("阿")]
t_stripped = [strip_trailing(x, heads) for x in teacher]

n = len(turns)
t_hi, t_lo = sum(map(len, teacher)), sum(map(len, t_stripped))
s_sum = sum(map(len, student))

print("===== 実測 =====")
print(f"ページ数            {len(texts)}")
print(f"置換文字(\N{REPLACEMENT CHARACTER})の数     {''.join(page_texts).count(chr(0xFFFD))}")
print(f"発話の数            {n}（先生 {len(teacher)} / 生徒 {len(student)}）")
print(f"発話数の比          先生 {len(teacher)/n*100:.1f}% / 生徒 {len(student)/n*100:.1f}%" if n else "")
print(f"先生の1発話の最長   {max(map(len, t_stripped)) if t_stripped else 0}字")
print(f"先生の文字数        {t_lo}〜{t_hi}字（見出しを外した側〜外さない側）")
print(f"生徒の文字数        {s_sum}字")
print(f"合計                {t_lo + s_sum}〜{t_hi + s_sum}字")
print(f"文字数の比          先生 {t_hi/(t_hi+s_sum)*100:.1f}% / 生徒 {s_sum/(t_hi+s_sum)*100:.1f}%" if (t_hi + s_sum) else "")
# 康熙部首の混入をどれだけ戻したか（17「現物と突き合わせた結果」1 の根拠）
raw_kx = set()
for mp in cmaps.values():
    for v in mp.values():
        raw_kx |= {c for c in v if 0x2F00 <= ord(c) <= 0x2FDF}
print(f"戻した康熙部首の種類  {len(raw_kx)}種")

# 先生の文末（17「現物と突き合わせた結果」3 の根拠）
DESU = r"(です|ます|ますね|ですね|ですか|ますか|でしょう|ません|ましょう|ましょうか|でした|ました|ください|下さい|ですよ|ますよ|でしょうか)$"
sents = [x for t in teacher for x in t.split("。") if x]
nonpolite = [x for x in sents if not re.search(DESU, x)]
print(f"先生の文の数          {len(sents)}（です・ます以外 {len(nonpolite)}）")

print()
print("===== 生徒の発話（全文） =====")
for x in student:
    print(" -", x)
print()
print("===== 先生の文のうち です・ます 以外（仕分けは 17 の表） =====")
for i, x in enumerate(nonpolite, 1):
    print(f"{i:2} |{x[-40:]}")

if len(sys.argv) > 2 and sys.argv[2] == "--text":
    print()
    print("===== 本文 =====")
    for num, t in texts:
        print(f"\n===== OBJ {num} =====")
        print(t)
