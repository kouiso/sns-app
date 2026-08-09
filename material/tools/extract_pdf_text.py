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
# ストリームの中身に、オブジェクトの見出しらしい並びが現れることがある。
# 本文に `(12 0 obj) Tj` と書いてあるだけ、という場合がそれにあたる。
# 全文をそのまま走査すると、それを本物の見出しと取り違えて本物を上書きする。
# 辞書が申告する /Length ぶんを読み飛ばしながら、順に拾う。
HDR = re.compile(rb"(?:^|[\s>])(\d+)\s+(\d+)\s+obj\b")
STREAM = re.compile(rb"stream\r?\n")
LEN = re.compile(rb"/Length\s+([^/>]+?)(?=/|>>)")


def scan_objects(resolve_len):
    out = {}
    pos = 0
    while True:
        m = HDR.search(data, pos)
        if not m:
            return out
        num, bstart = int(m.group(1)), m.end()
        sm = STREAM.search(data, bstart)
        eo = data.find(b"endobj", bstart)
        end = eo
        if sm and (eo == -1 or sm.start() < eo):
            lm = LEN.search(data, bstart, sm.start())
            n = resolve_len(lm.group(1)) if lm else None
            after = None
            if n is not None and sm.end() + n <= len(data):
                if b"endstream" in data[sm.end() + n:sm.end() + n + 32]:
                    after = sm.end() + n
            if after is None:
                after = data.find(b"endstream", sm.end())
                if after == -1:
                    stop(f"オブジェクト {num} に endstream がありません。")
            end = data.find(b"endobj", after)
        if end == -1:
            end = len(data)
        out[num] = data[bstart:end]
        pos = end + 6


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


# 1回目は直接書かれた長さだけで区切る。2回目はその結果を使って
# `/Length 12 0 R` のような間接参照も引けるようにする。
objs = scan_objects(lambda v: int(v) if v.strip().isdigit() else None)
objs = scan_objects(deref_int)


def filters_of(head):
    m = re.search(rb"/Filter\s*(/[A-Za-z0-9]+|\[[^\]]*\])", head)
    return re.findall(rb"/([A-Za-z0-9]+)", m.group(1)) if m else []


def stream_of(body, num=None, strict=True):
    """strict=False は「読めなければ None を返す」。対応表を探す最初の走査で使う。
    画像など、この道具が読む必要のないストリームまで止めないため。"""
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    start = m.end()
    head = body[:m.start()]
    # 圧縮の種類を見ずに中身を返すと、圧縮されたままの箱を本文として数える。
    # 本文が黙って消え、ページ数の検査は通ってしまう。
    unknown = [f for f in filters_of(head) if f != b"FlateDecode"]
    if unknown:
        if not strict:
            return None
        stop(f"オブジェクト {num} は未対応の圧縮です（{b','.join(unknown).decode()}）。")
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
    s = stream_of(body, num, strict=False)
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
    # 何バイトで1文字かは対応表が自分で宣言している。2バイト決め打ちにすると、
    # 1バイトの表で `<4142>` を1文字と読み違え、字数も文の数も狂う。
    widths = {len(a) // 2 for a, _ in re.findall(
        rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>",
        b"".join(re.findall(rb"begincodespacerange(.*?)endcodespacerange", s, re.S)))}
    if len(widths) > 1:
        stop(f"オブジェクト {num} の対応表が、1文字の長さを複数宣言しています。")
    cmaps[num] = (mp, widths.pop() if widths else 2)

font_to_cmap = {}
for num, body in objs.items():
    if b"/Type" in body and b"/Font" in body:
        m = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", body)
        if m and int(m.group(1)) in cmaps:
            font_to_cmap[num] = cmaps[int(m.group(1))]


def page_fontmap(body):
    out = {}
    # 世代番号は 0 とはかぎらない。0 だけを受けると、その字体の対応表を素通りして
    # 本文が化けたまま最後の検査を抜ける。
    for name, n in re.findall(rb"/([A-Za-z0-9#\.\-\+]+)\s+(\d+)\s+\d+\s+R", body):
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


def resolve_res(num):
    """フォントの定義はページに直接書かれているとは限らない。
    上位の /Pages に置いて子ページに継がせる書き方も正しい PDF なので、
    見つかるまで /Parent を上へ辿る。継承を見ないと、そのページだけ
    本文が読めずに黙って欠ける。"""
    seen = set()
    cur = num
    while cur is not None and cur not in seen:
        seen.add(cur)
        body = objs.get(cur, b"")
        m = re.search(rb"/Resources\s+(\d+)\s+\d+\s+R", body)
        if m:
            return objs.get(int(m.group(1)), b"")
        if re.search(rb"/Resources\s*<<", body):
            return body
        pm = re.search(rb"/Parent\s+(\d+)\s+\d+\s+R", body)
        cur = int(pm.group(1)) if pm else None
    return b""


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


ESC = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
       b"(": b"(", b")": b")", b"\\": b"\\"}


def literal_bytes(b):
    """PDF の ( ) 文字列から、逃がし記号と8進を戻して生のバイト列にする。
    そのまま読むと、逃がし記号と8進の数字が字数に混ざる。"""
    out, i = [], 0
    while i < len(b):
        ch = b[i:i + 1]
        if ch != b"\\":
            out.append(ch)
            i += 1
            continue
        nxt = b[i + 1:i + 2]
        if nxt in ESC:
            out.append(ESC[nxt])
            i += 2
        elif nxt in (b"\n", b"\r"):
            i += 2  # 行継続。何も出さない
        elif nxt in b"01234567":
            # `isdigit()` で受けると 8 と 9 まで通り、8進として読めずに落ちる。
            m = re.match(rb"[0-7]{1,3}", b[i + 1:])
            out.append(bytes([int(m.group(0), 8) & 0xFF]))
            i += 1 + len(m.group(0))
        else:
            i += 1  # 逃がし記号そのものは落とす
    return b"".join(out)


def decode_bytes(raw, cm):
    """本文のバイト列を字に直す。( ) で書かれていても < > で書かれていても、
    フォントに対応表が付いていればそれが正で、生のバイトではない。
    ( ) のときだけ対応表を無視すると、その部分が制御文字として数えられる。"""
    if not cm:
        return raw.decode("latin-1")
    mp, w = cm
    res = []
    for i in range(0, len(raw), w):
        code = int.from_bytes(raw[i:i + w].ljust(w, b"\0"), "big")
        if code in mp:
            res.append("".join(map(unify, mp[code])))
        else:
            res.append("\N{REPLACEMENT CHARACTER}")
    return "".join(res)


def decode_hex(h, cm):
    s = h.decode()
    if len(s) % 2:
        s += "0"  # PDF の規則。端数は 0 で埋める
    return decode_bytes(bytes.fromhex(s), cm)


# --- 本文の並びを切り分ける ----------------------------------------------
# ここは正規表現ではなく1文字ずつ読む。( ) の中に ( ) が入る書き方が正しい PDF で、
# 正規表現ではその文字列がまるごと一致せず、本文が黙って消えるためである。
# 消えても `�` は出ないので、置換文字の数では気づけない。
WS = b" \t\r\n\f\x00"
NAME = re.compile(rb"/([^\s/\[\]<>(){}%]*)")
NUM = re.compile(rb"[+-]?[\d\.]+")
OPER = re.compile(rb"[A-Za-z'\"][A-Za-z0-9*']*|\"|'")
EI = re.compile(rb"[\s>]EI(?=[\s\[\]/<(%]|$)")


def tokenize(buf, page):
    """演算子と、その手前に積まれる値に切る。返り値は (種類, 中身) の並び。"""
    toks, i, n = [], 0, len(buf)
    while i < n:
        c = buf[i:i + 1]
        if c in WS:
            i += 1
        elif c == b"%":
            j = buf.find(b"\n", i)
            i = n if j == -1 else j + 1
        elif c == b"(":
            j, depth, raw = i + 1, 1, bytearray()
            while j < n:
                ch = buf[j:j + 1]
                if ch == b"\\":
                    raw += buf[j:j + 2]
                    j += 2
                    continue
                if ch == b"(":
                    depth += 1
                elif ch == b")":
                    depth -= 1
                    if not depth:
                        j += 1
                        break
                raw += ch
                j += 1
            else:
                stop(f"ページ {page} の本文に、閉じていない丸括弧があります。")
            toks.append(("str", bytes(raw)))
            i = j
        elif buf[i:i + 2] in (b"<<", b">>"):
            i += 2
        elif c == b"<":
            j = buf.find(b">", i)
            if j == -1:
                stop(f"ページ {page} の本文に、閉じていない山括弧があります。")
            toks.append(("hex", re.sub(rb"\s", b"", buf[i + 1:j])))
            i = j + 1
        elif c in b"[]":
            toks.append(("op", c))
            i += 1
        elif c == b"/":
            m = NAME.match(buf, i)
            toks.append(("name", m.group(1)))
            i = m.end()
        elif c in b"+-0123456789.":
            m = NUM.match(buf, i)
            i = m.end() if m else i + 1
        else:
            m = OPER.match(buf, i)
            if not m:
                i += 1
                continue
            op = m.group(0)
            i = m.end()
            if op == b"BI":
                # 画像の生データ。本文の記号がたまたま混ざっていることがあるので、
                # 中を読まずに飛ばす。飛ばせなければ止める。
                d = buf.find(b"ID", i)
                e = EI.search(buf, d + 2) if d != -1 else None
                if not e:
                    stop(f"ページ {page} の画像データの終わりが見つかりません。")
                i = e.end()
                continue
            toks.append(("op", op))
    return toks


def xobject_map(res):
    """ページが呼び出せる図形部品の一覧。名前 -> オブジェクト番号。"""
    m = re.search(rb"/XObject\s+(\d+)\s+\d+\s+R", res)
    if m:
        src = objs.get(int(m.group(1)), b"")
    else:
        m = re.search(rb"/XObject\s*<<(.*?)>>", res, re.S)
        src = m.group(1) if m else b""
    return {n.decode(): int(o) for n, o in
            re.findall(rb"/([A-Za-z0-9#\.\-\+]+)\s+(\d+)\s+\d+\s+R", src)}


def read_content(content, res, page, depth=0):
    """本文の並びを字に直す。`Do` で呼ばれた部品の中にも本文が入るので、
    そこも読みに行く。読まないと、そのページは「成功」のまま字数だけ減る。"""
    if depth > 8:
        stop(f"ページ {page} の部品の呼び出しが深すぎます。")
    fm = page_fontmap(res)
    xm = xobject_map(res)
    cur = None
    out = []
    stack = []  # 演算子の手前に積まれた値

    def show(v):
        k, x = v
        if k == "hex":
            return decode_hex(x, cur)
        if k == "str":
            return decode_bytes(literal_bytes(x), cur)
        return ""

    for kind, val in tokenize(content, page):
        if kind != "op":
            stack.append((kind, val))
            continue
        if val == b"[":
            stack.append(("mark", b""))
        elif val == b"]":
            k = len(stack) - 1
            while k >= 0 and stack[k][0] != "mark":
                k -= 1
            items = stack[k + 1:] if k >= 0 else stack[:]
            del stack[k if k >= 0 else 0:]
            stack.append(("arr", items))
        elif val == b"Tf":
            if stack and stack[0][0] == "name":
                cur = fm.get(stack[0][1].decode())
            stack = []
        elif val == b"Tj":
            if stack:
                out.append(show(stack[-1]))
            stack = []
        elif val == b"TJ":
            if stack and stack[-1][0] == "arr":
                # 配列には16進の字とそのまま書いた字が混ざる。両方読む。
                out.extend(show(v) for v in stack[-1][1])
            stack = []
        elif val in (b"'", b'"'):
            # 改行してから1行出す書き方。読み飛ばすと、その行がまるごと消える。
            out.append("\n")
            if stack:
                out.append(show(stack[-1]))
            stack = []
        elif val in (b"TD", b"Td", b"T*", b"ET"):
            out.append("\n")
            stack = []
        elif val == b"Do":
            name = stack[0][1].decode() if stack and stack[0][0] == "name" else None
            stack = []
            onum = xm.get(name) if name else None
            if onum is None:
                continue  # 画像など、本文を持たない呼び出し
            sub = objs.get(onum)
            if sub is None:
                stop(f"ページ {page} が呼ぶ部品 {name}（オブジェクト {onum}）がありません。")
            if not re.search(rb"/Subtype\s*/Form\b", sub):
                continue  # 画像。本文は入っていない
            s = stream_of(sub, onum)
            if not s:
                stop(f"ページ {page} の部品 {name} の中身が取れません。")
            sres = resolve_res(onum)
            out.append(read_content(s, sres if sres else res, page, depth + 1))
        else:
            stack = []
    return "".join(out)


texts = []
for num in page_nums:
    body = objs[num]
    res = resolve_res(num)
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
    texts.append((num, read_content(content, res + body, num)))


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
