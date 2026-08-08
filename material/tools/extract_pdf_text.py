"""PDF の本文を標準ライブラリだけで取り出す。

使い方:  python3 extract_pdf_text.py <PDFのパス>

`17_文体正本の実測.md` の数値は、このスクリプトを
`変数と定数 _ver.1.0.0.pdf` に対して実行した結果から数えた。
PDF 本体は局長の著作物なのでリポジトリには入れていない。

このスクリプトは実測の証跡なので、**取りこぼしたら黙って続けない。**
数えられなかったものがあれば、その場で理由を出して止める。
"""
import re, zlib, sys, unicodedata

USAGE = "使い方: python3 extract_pdf_text.py <PDFのパス> [--text]"
if not 2 <= len(sys.argv) <= 3:
    sys.exit(USAGE)
# 綴り違いを黙って無視すると、本文が出ないのを仕様だと思い込む。
if len(sys.argv) == 3 and sys.argv[2] != "--text":
    sys.exit(f"知らない指定です: {sys.argv[2]}\n{USAGE}")
data = open(sys.argv[1], "rb").read()


def stop(msg):
    sys.exit(f"{msg}\n実測を中止します。")


# --- オブジェクトを集める ------------------------------------------------
# `endobj` を最初の一致で切ると、ストリームの中身にたまたま同じ並びがあったときに
# オブジェクトが途中で切れる。次のオブジェクトの見出しまでを本体とし、
# 末尾側の `endobj` で閉じる。
objs = {}
heads = [(m.start(), int(m.group(1))) for m in re.finditer(rb"(?:^|[\s>])(\d+)\s+(\d+)\s+obj\b", data)]
for i, (pos, num) in enumerate(heads):
    end = heads[i + 1][0] if i + 1 < len(heads) else len(data)
    chunk = data[pos:end]
    tail = chunk.rfind(b"endobj")
    body = chunk[:tail] if tail != -1 else chunk
    objs[num] = body[body.find(b"obj") + 3:]


def deref_int(v):
    """`/Length 12 0 R` のような間接参照を数値に直す。"""
    m = re.fullmatch(rb"\s*(\d+)\s*", v)
    if m:
        return int(m.group(1))
    m = re.fullmatch(rb"\s*(\d+)\s+\d+\s+R\s*", v)
    if m:
        t = objs.get(int(m.group(1)), b"")
        m2 = re.search(rb"\d+", t)
        return int(m2.group(0)) if m2 else None
    return None


def stream_of(body, num=None):
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    start = m.end()
    head = body[:m.start()]
    # 長さは辞書の /Length を正とする。endstream の最初の一致で切ると、
    # 圧縮データの中身にその並びが出たときにデータが欠ける。
    raw = None
    lm = re.search(rb"/Length\s+([^/>]+?)(?=/|>>)", head)
    if lm:
        n = deref_int(lm.group(1))
        if n is not None and start + n <= len(body):
            cand = body[start:start + n]
            if b"endstream" in body[start + n:start + n + 32]:
                raw = cand
    if raw is None:
        end = body.find(b"endstream", start)
        if end == -1:
            stop(f"オブジェクト {num} に endstream がありません。")
        raw = body[start:end]
    if b"FlateDecode" in head:
        # 途中まで展開できてもそれは本文の欠けた状態なので、採用せず止める。
        # 欠けたまま数えると、実測値が黙って小さく出る。
        try:
            return zlib.decompress(raw)
        except Exception as e:
            stop(f"オブジェクト {num} の展開に失敗しました（{e}）。")
    return raw


# --- フォントごとの ToUnicode 対応表 -------------------------------------
cmaps = {}  # ToUnicode のオブジェクト番号 -> 対応表
for num, body in objs.items():
    if b"beginbfchar" not in body and b"beginbfrange" not in body and b"/ToUnicode" not in body:
        # 展開してみないと分からないので、ストリームを持つものだけ試す
        if b"stream" not in body:
            continue
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

font_to_cmap = {}
for num, body in objs.items():
    if b"/Type" in body and b"/Font" in body:
        m = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", body)
        if m and int(m.group(1)) in cmaps:
            font_to_cmap[num] = cmaps[int(m.group(1))]


def page_fontmap(body):
    out = {}
    for name, n in re.findall(rb"/([A-Za-z0-9#\.\-\+]+)\s+(\d+)\s+0\s+R", body):
        n = int(n)
        if n in font_to_cmap:
            out[name.decode()] = font_to_cmap[n]
    return out


# --- ページを文書の順に並べる --------------------------------------------
# オブジェクト番号順に並べると、番号と綴じ順が違う PDF で本文の順序が入れ替わる。
# 1ページ目を目次として使っているので、順序が狂うと見出しの除去も話者の割り当ても狂う。
# /Pages の /Kids を辿って綴じ順を作る。
page_nums = []


def walk(num, seen):
    if num in seen:
        stop(f"ページの木が循環しています（オブジェクト {num}）。")
    seen.add(num)
    body = objs.get(num)
    if body is None:
        stop(f"ページの木から参照されたオブジェクト {num} がありません。")
    if re.search(rb"/Type\s*/Pages\b", body):
        km = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
        if not km:
            stop(f"オブジェクト {num} に /Kids がありません。")
        for kid in re.findall(rb"(\d+)\s+\d+\s+R", km.group(1)):
            walk(int(kid), seen)
    elif re.search(rb"/Type\s*/Page\b", body):
        page_nums.append(num)


root = None
for num, body in objs.items():
    if re.search(rb"/Type\s*/Pages\b", body) and b"/Parent" not in body:
        root = num
        break
if root is not None:
    walk(root, set())
    declared = deref_int(re.search(rb"/Count\s+(\d+)", objs[root]).group(1)) if re.search(rb"/Count\s+(\d+)", objs[root]) else None
    if declared is not None and declared != len(page_nums):
        stop(f"/Count は {declared} ページですが、辿れたのは {len(page_nums)} ページです。")
else:
    stop("ページの木の根（/Type /Pages）が見つかりません。")


def resolve_res(body):
    # /Resources が別オブジェクトなら引く。ページ本体に直接書いてあるなら本体を返す。
    m = re.search(rb"/Resources\s+(\d+)\s+0\s+R", body)
    if m:
        return objs.get(int(m.group(1)), b"")
    return body


def content_refs(body, num):
    """/Contents は単独参照と配列の両方の書き方がある。両方を読む。"""
    m = re.search(rb"/Contents\s*\[(.*?)\]", body, re.S)
    if m:
        return [int(x) for x in re.findall(rb"(\d+)\s+\d+\s+R", m.group(1))]
    m = re.search(rb"/Contents\s+(\d+)\s+\d+\s+R", body)
    if m:
        return [int(m.group(1))]
    m = re.search(rb"/Contents\s*<<", body)
    if m:
        stop(f"ページ {num} の /Contents が想定外の書き方です。")
    return []


kx_seen = set()  # 実際に本文で置き換えた康熙部首


def unify(c):
    """このPDFの対応表は「貝」「一」など複数の漢字を、字形の同じ康熙部首
    （U+2F00〜U+2FDF）で返してくる。見た目は同じだが別の文字なので、
    検索も比較もできない。通常の漢字へ戻す。"""
    if 0x2F00 <= ord(c) <= 0x2FDF:
        kx_seen.add(c)
        return unicodedata.normalize("NFKC", c)
    return c


ESC = {b"n": "\n", b"r": "\r", b"t": "\t", b"b": "\b", b"f": "\f",
       b"(": "(", b")": ")", b"\\": "\\"}


def decode_literal(b):
    """PDF の ( ) 文字列。バックスラッシュの逃がし方と8進を戻す。
    そのまま latin-1 で読むと、逃がし記号と8進が字数に混ざる。"""
    out, i = [], 0
    while i < len(b):
        ch = b[i:i + 1]
        if ch != b"\\":
            out.append(ch.decode("latin-1"))
            i += 1
            continue
        nxt = b[i + 1:i + 2]
        if nxt in ESC:
            out.append(ESC[nxt])
            i += 2
        elif nxt in (b"\n", b"\r"):
            i += 2  # 行継続。何も出さない
        elif nxt.isdigit():
            m = re.match(rb"[0-7]{1,3}", b[i + 1:])
            out.append(chr(int(m.group(0), 8)))
            i += 1 + len(m.group(0))
        else:
            i += 1  # 逃がし記号そのものは落とす
    return "".join(out)


def decode_hex(h, cmap):
    s = h.decode()
    res = []
    for i in range(0, len(s), 4):
        code = int(s[i:i + 4], 16)
        if cmap and code in cmap:
            res.append("".join(map(unify, cmap[code])))
        else:
            res.append("\N{REPLACEMENT CHARACTER}")
    return "".join(res)


TOK = (rb"/([A-Za-z0-9#\.\-\+]+)\s+[\d\.]+\s+Tf"
       rb"|<([0-9A-Fa-f]+)>\s*Tj"
       rb"|\[(.*?)\]\s*TJ"
       rb"|\(((?:\\.|[^()\\])*)\)\s*Tj"
       rb"|(TD|Td|T\*|ET)")

texts = []
for num in page_nums:
    body = objs[num]
    res = resolve_res(body)
    fm = page_fontmap(res + body)
    content = b""
    for cnum in content_refs(body, num):
        c = objs.get(cnum)
        if c is None:
            stop(f"ページ {num} の本文オブジェクト {cnum} がありません。")
        s = stream_of(c, cnum)
        if s:
            content += s + b"\n"
    if not content:
        continue
    cur = None
    out = []
    for tok in re.finditer(TOK, content, re.S):
        if tok.group(1):
            cur = fm.get(tok.group(1).decode())
        elif tok.group(2):
            out.append(decode_hex(tok.group(2), cur))
        elif tok.group(3):
            # 配列には16進の字とそのまま書いた字が混ざる。両方読む。
            for em in re.finditer(rb"<([0-9A-Fa-f]*)>|\(((?:\\.|[^()\\])*)\)", tok.group(3), re.S):
                if em.group(1) is not None:
                    out.append(decode_hex(em.group(1), cur))
                else:
                    out.append(decode_literal(em.group(2)))
        elif tok.group(4) is not None:
            out.append(decode_literal(tok.group(4)))
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
    stop("本文のあるページが1枚も取れませんでした。")
if len(texts) != len(page_nums):
    stop(f"{len(page_nums)} ページのうち {len(texts)} ページしか本文が取れませんでした。")

page_texts = [t for _, t in texts]
flat = re.sub(r"\s", "", "".join(page_texts))
turns = split_turns(flat)
if not turns:
    stop("「磯貝）」「阿部）」の話者ラベルが1件も見つかりません。")
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
print(f"発話数の比          先生 {len(teacher)/n*100:.1f}% / 生徒 {len(student)/n*100:.1f}%")
print(f"先生の1発話の最長   {max(map(len, t_stripped)) if t_stripped else 0}字")
print(f"先生の文字数        {t_lo}〜{t_hi}字（見出しを外した側〜外さない側）")
print(f"生徒の文字数        {s_sum}字")
print(f"合計                {t_lo + s_sum}〜{t_hi + s_sum}字")
print(f"文字数の比          先生 {t_hi/(t_hi+s_sum)*100:.1f}% / 生徒 {s_sum/(t_hi+s_sum)*100:.1f}%" if (t_hi + s_sum) else "")
# 本文で実際に置き換えた分だけを数える。対応表に載っているだけの字は数えない。
print(f"戻した康熙部首の種類  {len(kx_seen)}種")

# 先生の文末（17「現物と突き合わせた結果」3 の根拠）
# 「。」だけで切ると、「〜と思う？」のような文が次の文とくっついて数え落ちる。
TERM = "。！？!?"
# 敬体の語尾に「ね」「よ」「か」が付いた形を1つずつ並べると必ず取りこぼす。
# 語幹と終助詞を分けて書く。
DESU = r"(です|ます|ません|でしょう|ましょう|でした|ました|ませんでした|ください|下さい)(よ|ね|か|な)*$"
sents = [x for t in teacher for x in re.split(f"[{TERM}]", t) if x]
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
