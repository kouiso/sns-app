#!/usr/bin/env python3
"""check_g4_receipt.py の退行テスト。

止めるもの（未記入・観点表の欠落・同一ファミリー・回数超過・R3 FAIL の §7 未記入・
総合判定の矛盾・不明な章IDのファイル名）と、止めてはいけないもの（記入済みの
受領証・エスカレーション不要ラウンドの §7 雛形・空の g4/ ディレクトリ）の両方を
置く。片方だけでは、全部を止める検査でも全部を通す検査でも緑になってしまう。

フィクスチャは material/reviews/_template_G4受領証.md の構造を写し、
<...> の欄に実値を入れた形にする。
"""

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_g4_receipt  # noqa: E402
from check_g4_receipt import check_g4_dir  # noqa: E402

CID = "known-chapter"
TAG = f"chapter/{CID}"
LIVE = {CID}

# ## 7. の雛形（テンプレートどおり未記入）。エスカレーション不要なラウンドでは
# このまま残るのが正しい姿なので、有効な受領証の中にも置いておく。
S7_TEMPLATE = """## 7. 局長エスカレーション（R3 も FAIL のときだけ記入）

| 項目 | 値 |
|---|---|
| エスカレーション日 | <YYYY-MM-DD> |
| 残っている FAIL 観点 | |
| 渡した資料 | <受領証のパス・章のパス・3ラウンドの差分> |
| 局長の裁定 | <未回答 / 内容> |
| 裁定後の処置 | |
"""

S7_FILLED = """## 7. 局長エスカレーション（R3 も FAIL のときだけ記入）

| 項目 | 値 |
|---|---|
| エスカレーション日 | 2026-10-01 |
| 残っている FAIL 観点 | 文体逸脱 |
| 渡した資料 | material/reviews/g4/known-chapter.md と3ラウンドの差分 |
| 局長の裁定 | 未回答 |
| 裁定後の処置 | 局長の裁定待ち |
"""


def _block(n, *, tag=TAG, family="Codex/GPT系", gen="Claude",
           tech="PASS", conn="PASS", style="PASS",
           q1="到達できる", q2="無し", q2c="-", q3="無し", q3c="-",
           verdict="PASS", action="G5 へ進む", s7="template", include_s5=True):
    """テンプレートの # R<n> ブロックに実値を入れたもの。s7 は
    "template"=雛形のまま / "filled"=記入済み / None=節ごと無し。"""
    s5 = "## 5. 退屈だった箇所（**合否に数えない**）\n\n- 無し\n\n" if include_s5 else ""
    s7_text = {"template": S7_TEMPLATE, "filled": S7_FILLED}.get(s7, "")
    return f"""# R{n}（2026-09-2{n}）

## 1. 実施条件

| 項目 | 値 |
|---|---|
| 対象タグ | `{tag}` |
| 教材ドラフトのコミット | `abc{n}def` |
| 使ったAIファミリー | {family} |
| 指定か代替か | 指定 |
| モデル名・版 | gpt-5-codex |
| 実行経路 | CLI |
| 生成側ファミリー | {gen} |

## 2. 渡した入力（渡していないものも記録する）

- [x] 教材ドラフト本文（embedmd 展開後。読者が読む形）
- [x] `listings/{CID}/` の全ファイル
- [x] 章分割表の当該行（完成する状態 / 前提とする前章成果）
- [x] `12_文体・AI臭さ排除方針.md`
- [x] 前章までの章タイトル一覧
- [x] 前ラウンドの指摘と処置内容（R1 は該当なし、以降は前回分を同梱）

渡していないことの確認（渡したら G4 は無効）:

- [x] `dev-logs/{CID}.md` を渡していない
- [x] 設計書を渡していない
- [x] 生成側のセッション文脈・生成プロンプト・推敲途中版を渡していない
- [x] 対照版を渡していない
- [x] 他の章と束ねずにこの章だけを1回の発注で渡した

## 3. 観点別 PASS/FAIL（合否を数えるのはこの3つ）

| 観点 | 判定 | 根拠 |
|---|---|---|
| 技術正確性 | {tech} | 記述どおり動く |
| 完成品へのつながり | {conn} | 完成状態に一致する |
| 文体逸脱 | {style} | 逸脱なし |

### 3.1 引用範囲の過不足

| 設問 | 判定 | 内容 |
|---|---|---|
| 教材だけを読んで写した読者が、章末の状態に到達できるか | {q1} | - |
| 引用に含まれていないのに動作に要る行があるか | {q2} | {q2c} |
| `listings/{CID}/` の中で覆われていないファイルがあるか | {q3} | {q3c} |

## 4. 指摘一覧

| # | 重大度 | 箇所 | 指摘 | 判断 | 処置 | 処置コミット |
|---|---|---|---|---|---|---|
| - | - | - | 指摘なし | - | - | - |

{s5}## 6. 総合判定と次のアクション

| 項目 | 値 |
|---|---|
| 総合判定 | {verdict} |
| このラウンド後の修正回数 | {n - 1}/2 |
| 次のアクション | {action} |

{s7_text}"""


def receipt(*blocks, last_overall=None):
    """台帳＋ラウンド一覧＋# R<n> ブロックを組み立てる。各 dict は _block の kwargs。"""
    rows, parts = [], []
    for i, kw in enumerate(blocks, 1):
        rows.append(f"| R{i} | `{kw.get('tag', TAG)}` | `abc{i}def` | 2026-09-2{i} "
                    f"| 指定・Codex/GPT系 | {kw.get('verdict', 'PASS')} | {i - 1}/2 |")
        parts.append(_block(i, **kw))
    overall = last_overall or blocks[-1].get("verdict", "PASS")
    return f"""# G4 受領証 — 章 `{CID}`

検査用のフィクスチャ。

## 台帳（章ごとに1つ。ラウンドを追記する）

| 項目 | 値 |
|---|---|
| 章ID | `{CID}` |
| 章タイトル | 検査用の章 |
| 教材本文 | `curriculum/{CID}.md` |
| 引用元 | `listings/{CID}/` |
| 最新ラウンド | R{len(blocks)} |
| 現在の総合判定 | {overall} |

### ラウンド一覧（修正回数のカウンタ）

| ラウンド | 対象タグ | 教材ドラフトのコミット | 実施日 | ファミリー | 総合判定 | 修正回数 |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

---

{chr(10).join(parts)}
"""


VALID = receipt(dict(verdict="PASS"))

# R3 まで FAIL を重ねた受領証（同一対象タグ）。R1/R2 の §7 は雛形のまま残る
# （エスカレーション不要のラウンドでは未記入が正しい姿）。
THREE_FAIL = receipt(
    dict(verdict="FAIL", style="FAIL", action="修正して R2 を発注"),
    dict(verdict="FAIL", style="FAIL", action="修正して R3 を発注"),
    dict(verdict="FAIL", style="FAIL", action="局長エスカレーション"),
    last_overall="エスカレーション中",
)
THREE_FAIL_FILLED = receipt(
    dict(verdict="FAIL", style="FAIL", action="修正して R2 を発注"),
    dict(verdict="FAIL", style="FAIL", action="修正して R3 を発注"),
    dict(verdict="FAIL", style="FAIL", action="局長エスカレーション", s7="filled"),
    last_overall="エスカレーション中",
)
THREE_FAIL_NO_S7 = receipt(
    dict(verdict="FAIL", style="FAIL", action="修正して R2 を発注"),
    dict(verdict="FAIL", style="FAIL", action="修正して R3 を発注"),
    dict(verdict="FAIL", style="FAIL", action="局長エスカレーション", s7=None),
    last_overall="エスカレーション中",
)

# (ケース名, {ファイル名: 本文}, live_ids, 指摘に含まれるべき文字列の一覧)
# 一覧が空なら「指摘0件」を期待する。
CASES = [
    (
        "記入済みの PASS 受領証は通す（§7 雛形が残っていてもよい）",
        {f"{CID}.md": VALID},
        LIVE,
        [],
    ),
    (
        "<...> が残っていれば止める（D15-8-3）",
        {f"{CID}.md": VALID.replace("gpt-5-codex", "<モデル名>")},
        LIVE,
        ["プレースホルダ"],
    ),
    (
        "空の表セルがあれば止める（D15-8-3）",
        {f"{CID}.md": VALID.replace("| 実行経路 | CLI |", "| 実行経路 |  |")},
        LIVE,
        ["空の表セル"],
    ),
    (
        "「未記入」があれば止める（D15-8-3）",
        {f"{CID}.md": VALID.replace("指摘なし", "未記入")},
        LIVE,
        ["未記入"],
    ),
    (
        "§3 の観点行が欠けたら止める（D15-8-4）",
        {f"{CID}.md": VALID.replace("| 文体逸脱 | PASS | 逸脱なし |\n", "")},
        LIVE,
        ["文体逸脱"],
    ),
    (
        "§3 に数えない観点を足したら止める（退屈度は合否に数えない。D15-3）",
        {f"{CID}.md": VALID.replace(
            "| 文体逸脱 | PASS | 逸脱なし |",
            "| 文体逸脱 | PASS | 逸脱なし |\n| 退屈度 | PASS | - |")},
        LIVE,
        ["退屈度"],
    ),
    (
        "§3 の判定が PASS/FAIL 以外なら止める（D15-8-4）",
        {f"{CID}.md": VALID.replace("| 技術正確性 | PASS |", "| 技術正確性 | OK |")},
        LIVE,
        ["PASS/FAIL"],
    ),
    (
        "レビュアと生成側が同一ファミリーなら止める（16 A6, D15-6）",
        {f"{CID}.md": VALID.replace(
            "| 使ったAIファミリー | Codex/GPT系 |", "| 使ったAIファミリー | `Claude` |")},
        LIVE,
        ["同一ファミリー"],
    ),
    (
        "§3.1 で「有り」なのに技術正確性が PASS なら止める（D15-8-5）",
        {f"{CID}.md": receipt(dict(q2="有り", q2c="src/app/a.ts:3"))},
        LIVE,
        ["技術正確性"],
    ),
    (
        "総合判定 PASS なのに観点 FAIL があれば止める（D15-8-7）",
        {f"{CID}.md": receipt(dict(style="FAIL", verdict="PASS"))},
        LIVE,
        ["FAIL 観点"],
    ),
    (
        "同一対象タグの4ラウンド目は止める（D15-4, D15-8-6）",
        {f"{CID}.md": receipt({}, {}, {}, {})},
        LIVE,
        ["R3 まで"],
    ),
    (
        "R3 FAIL で §7 が未記入なら止める（10:211-212, D15-8-6）",
        {f"{CID}.md": THREE_FAIL},
        LIVE,
        ["D15-8-6"],
    ),
    (
        "R3 FAIL で §7 自体が無くても止める（10:211-212, D15-8-6）",
        {f"{CID}.md": THREE_FAIL_NO_S7},
        LIVE,
        ["局長エスカレーション"],
    ),
    (
        "R3 FAIL で §7 が記入済みならその検査は通す",
        {f"{CID}.md": THREE_FAIL_FILLED},
        LIVE,
        [],
    ),
    (
        "§5 退屈だった箇所 が無ければ止める（記録必須欄。D15-3）",
        {f"{CID}.md": receipt(dict(include_s5=False))},
        LIVE,
        ["退屈"],
    ),
    (
        "一覧に無い # R ブロックは止める（カウンタは一覧の行数。D15-4）",
        {f"{CID}.md": VALID + "\n" + _block(2)},
        LIVE,
        ["ラウンド一覧"],
    ),
    (
        "一覧に無い basename（章IDでないファイル名）は止める（D15-8-1）",
        {"stray-chapter.md": VALID},
        LIVE,
        ["章ID"],
    ),
    (
        "章IDが一致する basename は通す",
        {f"{CID}.md": VALID, "README.md": "# 置き場の説明\n"},
        LIVE,
        [],
    ),
]


def run_main(args):
    """main() の終了コードだけを見る。検査自身の ✅/❌ 出力は捨てる。"""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return check_g4_receipt.main(["check_g4_receipt.py", *args])


def check_exit_code() -> tuple[int, int]:
    """main() 経由の終了コードを見る。(失敗数, 実行ケース数) を返す。

    空の g4/ は「受領証がまだ無い」正常な状態なので 0、g4/ 自体が無いのは
    環境異常なので 2、--target の受領証欠落は違反なので 1 を返すはず。
    """
    failed = 0
    total = 0

    def expect(name, want, got):
        nonlocal failed, total
        total += 1
        if got != want:
            failed += 1
            print(f"  ❌ {name}: 終了コード {want} を期待、実際 {got}")

    with tempfile.TemporaryDirectory() as d:
        expect("空の g4/ ディレクトリは PASS", 0, run_main(["--g4-dir", d]))
    with tempfile.TemporaryDirectory() as d:
        Path(d, "README.md").write_text("# 置き場\n", encoding="utf-8")
        expect("README.md だけの g4/ も PASS", 0, run_main(["--g4-dir", d]))
    expect("g4/ 自体が無ければ 2", 2, run_main(["--g4-dir", "/no/such/g4-dir"]))
    with tempfile.TemporaryDirectory() as d:
        expect("--target の受領証が無ければ 1", 1,
               run_main(["--g4-dir", d, "--target", "text-post"]))
    with tempfile.TemporaryDirectory() as d:
        # text-post は実在する生きている章ID。中身の章ID記録とファイル名の
        # 一致は検査していないので、VALID のまま置ける。
        Path(d, "text-post.md").write_text(VALID, encoding="utf-8")
        expect("--target の受領証があれば 0", 0,
               run_main(["--g4-dir", d, "--target", "text-post"]))
    with tempfile.TemporaryDirectory() as d:
        Path(d, "stray.md").write_text(VALID, encoding="utf-8")
        expect("違反があれば 1", 1, run_main(["--g4-dir", d]))
    return failed, total


def main() -> int:
    failed = 0
    for name, files, live, wants in CASES:
        with tempfile.TemporaryDirectory() as d:
            for fname, body in files.items():
                Path(d, fname).write_text(body, encoding="utf-8")
            findings = check_g4_dir(Path(d), live)
        messages = [m for _, _, m in findings]
        missing = [w for w in wants if not any(w in m for m in messages)]
        if missing or (not wants and findings):
            failed += 1
            print(f"  ❌ {name}")
            for w in missing:
                print(f"     期待する指摘が無い: {w}")
            for fname_, line, m in findings:
                print(f"     指摘: {fname_}:{line} {m}")
    exit_failed, exit_total = check_exit_code()
    failed += exit_failed
    total = len(CASES) + exit_total
    if failed:
        print(f"❌ check_g4_receipt 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_g4_receipt 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
