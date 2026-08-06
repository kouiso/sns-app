# task-app 資産の棚卸しと移植記録

作成: 2026-08-05
対象: `kouiso/task-app`（前作＝タスク管理アプリ＝Redmineモドキの30日教材）が持つ
執筆スキル・強制フック・検査スクリプト・設定のうち、本作へ持ち込むもの。

## 0. なぜこの棚卸しが要ったか

`10_教材制作フロー.md` は前作の**手戻り16件**を対策表として引き継いだ。しかし
**前作が実際に作った道具**は引き継いでいなかった。棚卸しの結果、次の差が判明した。

| 資産 | task-app | sns-app（棚卸し前） |
|---|---|---|
| 執筆スキル | material-writing（外部パック2本＋voice-spec 込み・272KB） | 無し |
| 強制フック | 4本 | 無し |
| 検査スクリプト | 28本（＋テスト17本） | `check_tone.py` 1本 |
| textlint 設定 | preset-ja-technical-writing ＋ **preset-ai-writing** | preset-ja-technical-writing ＋ prh のみ |
| 監査運用 | クリーンルーム通し実行3区間・blind-test 6ラウンド | G6 未完走 |

`10_教材制作フロー.md` G0 が要求していた道具は **4種**（textlint / embedmd /
章末スナップショット生成 / G6実走ランナー）である。**この4種を全部揃えても、
前作が実測で見つけた欠陥型は1つも検出できない。** G0 の改訂が要る（B31）。

### この棚卸しは、捨て試作での反復の空回りも説明する

`PROGRESS.md` は 2026-07-28 に、Round 12〜19 の指摘が
`prototype-chapter/tools/g5-quote.sh` へ集中したことを「捨てる予定の道具を
磨き続けた」と記録した。棚卸しの結果、より正確な説明が付く。
**前作にテスト付きの検査群が28本あるのに、それを見ずに作り直していた。**
「丁寧さの空回り」ではなく「手元の資産の未把握」であり、こちらは再発を防げる。

## 1. 移植したもの（このコミット）

| 資産 | 移植先 | 変更点 |
|---|---|---|
| `material-writing` スキル一式（272KB） | `.claude/skills/material-writing/` | 無変更。hana652-tech-writing-pack（CC BY 4.0・guides 6本＋`ai-smell-lint.py`）と xamfonos-technical-writing-best-practices、`references/voice-spec.md` を含む |
| 強制フック4本 | `.claude/hooks/` | 対象ディレクトリと印の置き場を変更（§2） |
| フックの配線 | `.claude/settings.json` | 新規。PreToolUse(Write/Edit/Bash) と PostToolUse(Skill) |
| 検査スクリプト28本＋テスト17本 | `scripts/curriculum-qa/` | 無変更で搬入。**動く保証はまだ無い**（§4 の分類が済むまで実行しない）。**★ 2026-08-06: Vivliostyle 採用でも「Markdown を読む」という前提は崩れない**（Vivliostyle の入力も Markdown＝VFM）。実際に効くのは2点で、(1) `check_zip_reference.py` / `sale_package.py` / `check-sale-package.sh` の配布形式前提（§4 で移植先を確定）(2) `markdown_scan.paragraphs()` が frontmatter を地の文1段落として返すこと（実測）。ただし **12 §1.1.1 で教材本文の frontmatter を禁止した**ので (2) は当面顕在化しない。`check_tone.py` は VFM 記法入りでも同判定（陰性 rc=0 / 陽性 rc=1・22件検出）を実測済み。**残り26本は VFM 記法（ルビ・`ts:パス` 形式のフェンス・`{.class}`）を通せるか未実測** — 教材本文が1文字も無く検査が想定するディレクトリ構成を作れないため。特に `check_tag_balance.py`（波括弧をタグとして誤って数える可能性）と `check_ja_line_break.py`（VFM は段落内の改行の意味が違う）は骨格ができた時点で必ず実測しなおす。B31 の分類の入力にする |
| textlint 設定 | `.textlintrc.json` | 本作の既存設定（prh 辞書・sentence-length 100）へ **`@textlint-ja/preset-ai-writing` を追加**して統合 |

## 2. フックの変更点（ここだけは無変更で持ち込めない）

**task-app の `material/30days-curriculum/` が教材本文だったのに対し、本作の
`material/` は設計文書（00〜16・PROGRESS・承認パッケージ）であって教材本文ではない。**
無変更で持ち込むと、設計文書の編集がすべて deny される。

| 項目 | task-app | sns-app |
|---|---|---|
| 監視対象 | `material/**/*.md` | `curriculum/**/*.md` |
| 起動条件 | `material/30days-curriculum/` の存在 | `curriculum/` の存在 |
| 印の置き場 | `$TMPDIR/task-app-material-writing-loaded-$(id -u)` | `$TMPDIR/sns-app-...` |
| cwd ガード | `*task-app*` | `*sns-app*` |

`curriculum/` は**教材本文の置き場としての暫定名**である。確定は B1（章分割表の凍結）
および B2（リポジトリ構造）。ディレクトリが存在しない間このゲートは不活性で、
作られた時点で自動的に効き始める。**確定した名前が `curriculum/` 以外になったら、
4本のフックと本表を同じPRで直すこと。**

### 検知テスト（G0 が要求する陽性/陰性サンプル）

`.claude/hooks/material-writing-gate.sh` に対し、6件を実際に流して確認した。

| # | 入力 | 期待 | 結果 |
|---|---|---|---|
| 1 | `curriculum/` が存在しない状態で `curriculum/ch01.md` へ Write | 通す（不活性） | 通した |
| 2 | `curriculum/ch01.md` へ Write（印なし） | **deny** | deny |
| 3 | **`material/00_企画概要.md` へ Write（印なし）** | **通す** | 通した |
| 4 | `python3 -c ... > curriculum/ch01.md`（シェル経由の抜け道） | **deny** | deny |
| 5 | `grep foo curriculum/ch01.md`（読むだけ） | 通す | 通した |
| 6 | `curriculum/ch01.md` へ Write（印あり） | 通す | 通した |

3 が本作固有の回帰検査にあたる。ここが deny になると設計文書が書けなくなる。

## 3. 移植しなかったもの（と、その理由）

| 資産 | 判断 | 理由 |
|---|---|---|
| `.claude/rules/` 11本 | **移さない** | core-mission / persona / prohibitions / workflow / technical-regulations は利用者の `~/.claude/skills/` に同名で存在し、全セッションで有効。リポジトリへ複製すると二重管理になり、文脈も食う。`prisma.instructions.md` は本作に該当しない（Supabase 構成） |
| `.claude/agents/` 15本・`commands/` 30+本 | **保留** | 本作に要る数はこれより少ない。必要になったものだけ後追いで入れる |
| `.claude/skills/article-writing` | **保留** | 記事・ブログ向けの汎用ボイス取り込みスキルで、教材のレジスタとは別物。`material-writing` の description も「教材以外の文章には使わない（レジスタが違う）」と明示している |
| `.claude/contexts/` 3本 | **保留** | 中身の評価が済んでいない |

## 4. 検査スクリプト28本の分類（B31 で1本ずつ決める）

搬入は済んでいるが、**本作で動く保証はまだ無い。** 前作は Next.js + tRPC + shadcn/ui、
本作は Expo(React Native) + Supabase であり、前提が違うものが混ざっている。

**2026-08-06 改訂（D14）**: 初版の分類は docstring から導いたもので実走していなかった。
28本すべてを実際に走らせ、依存・命名前提・0件走査の挙動を測り直した。生の出力は
`decisions/D14_検査スクリプトの実走結果.md`。初版が覆っていたのは25本で、
`markdown_scan.py` / `curriculum_blocks.py` / `gen_procedure_map.py` の3本が表に無かった。
**実走で ◎ に残ったのは15本ではなく5本である。**

区分: ◎ そのまま効く／○ 手直しが要る／△ 作り直しが要る／× 本作では使わない

### ◎ そのまま効く（5本）

| スクリプト | 何を見るか | 依存する他スクリプト | 外部ファイル依存 | D1命名での挙動 | 0件走査 |
|---|---|---|---|---|---|
| `markdown_scan.py` | フェンス・段落・インラインコードの走査。**20本が import する土台**。単体では走らない | 無し（標準ライブラリのみ） | 無し | 入力を見ないので無関係 | — |
| `check_tone.py` | 関西弁・タメ口・AI構文（**本作へ移植済みの1本**） | `markdown_scan` | 無し | 1ファイル入力で動く。実入力で1件検出 rc=1 | 該当なし（1ファイル専用） |
| `check_variants.py` | 同じ語の表記ゆれ（「すでに」46件に対し「既に」21件の混在を実測） | `markdown_scan` | 無し | `*.md` glob。ディレクトリ入力で動く rc=0（2ファイル） | 対象0件で rc=2（fail closed） |
| `check_step_length.py` | コードブロックが長すぎないか | 無し | 無し | 1ファイル入力で動く（6ブロック判定） | 該当なし |
| `check_visualization.py` | 表・図の量 | 無し | 無し | 1ファイル入力で動く。実入力で不足2件 rc=1 | 該当なし |

### ○ 手直しが要る（17本）

| スクリプト | 手直しの内容 | 依存する他スクリプト | 外部ファイル依存 | D1命名での挙動 | 0件走査 |
|---|---|---|---|---|---|
| `curriculum_blocks.py` | `day_number()` が `dayNN` 以外に **0** を返し、章の前後関係が消える。章分割表の並び順を引く形へ | `markdown_scan` | 無し | 全章が 0 に潰れる。警告なし | — |
| `check_why.py` | コード直後の「なぜ」。**外部レビューの「翻訳文感」の実体はここだと前作が特定**。ディレクトリ glob が `day[0-9][0-9]_*.md` | `markdown_scan` | 無し | ディレクトリ入力で `対象ファイルがありません` rc=2 | rc=2（fail closed） |
| `check_step_ref.py` | 本文が指す Step 番号がその章に在るか。glob 同上 | `markdown_scan` | 無し | 同上 rc=2 | rc=2 |
| `check_crossref.py` | 章間の参照先が実在するか。glob が `day/00*/appendix_*` | `markdown_scan` | 無し | `dayファイルが見つかりません` rc=2 | rc=2 |
| `check_terms.py` | 同じ概念に2通りの書き方。glob 同上 | `markdown_scan` | 無し | `教材ファイルが見つかりません` rc=2 | rc=2 |
| `check_step_time.py` | 所要時間の表と本文の合計。**番号ベースの暗黙免除（`NO_TABLE_DAYS`）が D1 命名で全章へ広がる** | `markdown_scan` | 無し | ディレクトリ rc=2／**1ファイルは `✅ OK（0 ファイル）` rc=0** | **緑になる（要修正）** |
| `check_anchor.py` | 書き込み先がそのブロックだけで分かるか。プレフィックスが `src/ prisma/ scripts/` 固定で、D1-5 の `app/ supabase/` に1件も当たらない | `markdown_scan`（`FILEPATH` は自前で重複定義） | **リポジトリ根の実ファイル**（存在確認） | `*.md` glob で走るが検出0 rc=0 | **緑になる（要修正）** |
| `check_comprehension.py` | 初心者向けの数値基準。Step 見出しが無いと丸ごとスキップ。用語リストが Next.js/tRPC/shadcn 寄り（:20-21） | 無し | 無し | 1ファイル専用。`チェックスキップ` rc=0 | **緑になる（要修正）** |
| `check_no_skip.py` | ステップの連続性。0本でも合格を印字 | `curriculum_blocks` | 無し | 1ファイル専用。`全0ステップが完全` rc=0 | **緑になる（要修正）** |
| `check_code_completeness.py` | `filepath:` コメントの有無・分割禁止。**1つも無くても警告どまりで PASS** | `curriculum_blocks` | 無し | 1ファイル専用 rc=0 | **緑になる（要修正）** |
| `check_tech_stack.py` | Next.js / shadcn/ui 前提 → Expo / React Native へ。**未検出でも PASS するので本作では常に緑** | 無し | 無し | 1ファイル専用 rc=0 | **緑になる（要修正）** |
| `check_unused_image.py` | 参照されていない画像。本体は `rglob("*.md")` で命名非依存 | `markdown_scan` | 入力配下の `screenshots/`。**自己テストが `.github/workflows/material-gate.yml`（前作のワークフロー名）を読んで落ちる** | `screenshots` 不在で rc=2 | rc=2 |
| `check_ja_line_break.py` | JSX 内の日本語途中改行。**React Native でも同じ事故が起きる**が、判定対象の要素名が違う | `markdown_scan` | 無し | `rglob("*.md")` で走る rc=0 | 対象0件で rc=2 |
| `check_jsx_marker.py` | 同上 | `markdown_scan` | 無し | 同上 rc=0 | rc=2 |
| `check_tag_balance.py` | 同上。**加えて `sale_package`（△）へ依存し、値が要求された時点で `build-zip.sh` 欠落で落ちる** | `curriculum_blocks`, **`sale_package`(△)** | `scripts/build-zip.sh`（遅延） | ディレクトリ rc=2／1ファイルで `FileNotFoundError` rc=1 | rc=2 |
| `check_false_success.py` | 構造が閉じていない時点で「これでエラーが出なくなります」と書いていないか。**`check_tag_balance` 経由で `sale_package`(△) に依存**し、△を作り直すまで1回も完走しない | `check_tag_balance`, `curriculum_blocks`, `markdown_scan` | `scripts/build-zip.sh`（遅延） | ディレクトリ rc=2／1ファイルで `FileNotFoundError` rc=1 | rc=2 |
| `check_scaffold_curriculum_alignment.py` | scaffold の概念が本作に無い。A7 の章末スナップショットへ読み替え | `curriculum_blocks` | `scripts/scaffold-from-scratch.sh` / `package.json` / `material/30days-curriculum/day*.md` / `src/` 4ファイル。**全部無い** | 引数を見ずに `FileNotFoundError` rc=1 | — |
| `check_quality.sh` | 統合スクリプト。**`day[0-9][0-9]_*.md` 以外の .md を検出すると即 exit 1**（:26-38）。D1 の章IDではディレクトリ入力を1件も通さない。さらに day ファイルが無いと corpus 検査14本を黙って飛ばす（:266-271） | 単体22本＋自己テスト17本を呼ぶ | 無し | ディレクトリ入力 rc=1（命名拒否） | **corpus 14本が黙ってスキップ（要修正）** |

`○` は17本になった（初版6本 + ◎からの降格10本 + 表外の `curriculum_blocks.py`）。

### △ 作り直しが要る（4本）

> **★ 2026-08-06 追記: 下表のうち ZIP を土台にする3本は、移植先が確定した。**
> 16 B9 が決着し（教材本文＝PDF が正本、EPUB を機械検査用に併産。
> `decisions/D23_Vivliostyle採用の影響.md`）、**作り直す対象は ZIP ではなくなった。**
>
> | スクリプト | 新しい区分 | 根拠 |
> |---|---|---|
> | `sale_package.py` | **EPUB 版へ移植** | 実測で **EPUB は ZIP フォーマット**であり、本文の `<code>` / `<pre>` / 相対 `href` が XHTML にそのまま残る。「パッケージのエントリ名を読む」という発想はほぼそのまま動く（`zipfile.ZipFile(...).namelist()` で確認） |
> | `check_zip_reference.py` | **EPUB 版へ移植 ＋ PDF 版を新規** | 本文参照とパッケージ内容の照合は EPUB に対してなら移植できる。**PDF に対しては別実装が要る** — PDF は原稿の構造を失う（バッククォートが消えて `src/` が裸になり、行の折り返しで文が分断されて grep が当たらない。実測）ので文字列照合が偽陰性を出す。PDF 側はリンク注釈を `pdftohtml -stdout -i -noframes` で列挙する検査になる（`pdftotext` にはリンク文字列しか出ず URL が取れない） |
> | `check-sale-package.sh` | **廃止** | 前作の ZIP ファイル名 `task-app-curriculum-v1.1.zip` を直書きしており、移植する中身が無い |
>
> **`check_procedure_order.py` は上の話と無関係**（tRPC 前提の読み替え）なので区分は変わらない。
>
> **検査の層を分けること**（D23 §2-8）: 28本＋G3/G5 は **Markdown 原稿にのみ**走らせ続け、
> PDF には走らせない。PDF / EPUB には別建ての薄い配布物検査を新設する（16 B53）。
>
> **なお `check_tag_balance.py` / `check_false_success.py` が今まったく動かない理由は
> 引数仕様ではない。** `check_tag_balance.py:183` → `sale_package.py:66` の
> `BUILD_ZIP.read_text` が未搬入の `scripts/build-zip.sh` を読みにいって
> `FileNotFoundError` で落ちる（＝この△の欠落と同根）。
> **「教材本文ができれば動く」という期待は成立しない。**`sale_package.py` の移植が先である。

| スクリプト | 理由 | 依存する他スクリプト | 外部ファイル依存 | D1命名での挙動 | 0件走査 |
|---|---|---|---|---|---|
| `sale_package.py` | ZIP の中身を `build-zip.sh` から読む土台。**`check_tag_balance` / `check_false_success` / `check_zip_reference` の3本がこれを経由する。◎/○ を先に配線しても、これを作り直すまで起動しない** | `check_scaffold_curriculum_alignment`(○) | `scripts/build-zip.sh`。**無い** | 入力を見ない | — |
| `check_zip_reference.py` | **前作の30周目で見つかった最も重い1件**（本文8箇所が「リポジトリの `src/` と見比べて」と書いていたが、販売ZIPにその照合先が入っていない）に対応。本作は配布が**3系統**に分かれるため1系統前提では成立しない | `sale_package`, `markdown_scan` | `scripts/build-zip.sh`（遅延） | `*.md` glob で走る。**当たりが無いと rc=0 で緑、1件でも当たると `FileNotFoundError` rc=1** | **違反ゼロと未判定が同じ出力（要修正）** |
| `check-sale-package.sh` | 同上。ZIP のエントリ名を直接照合する。前作のファイル名 `task-app-curriculum-v1.1.zip` と `scripts/_*` 13ディレクトリが前提 | 無し | ZIP 本体・`scripts/_*` 13ディレクトリ。**全部無い** | `販売用 ZIP が見つかりません` rc=1 | — |
| `check_procedure_order.py` | tRPC の手続き前提（`src/server/api/routers/*.ts` の filepath を読む）。Supabase SDK 呼び出しと RLS ポリシーへ読み替え | `markdown_scan` | 無し | ディレクトリ rc=2／**1ファイルは `手続き 0 個` rc=0。Supabase 構成では常に0件＝常に緑** | **緑になる（要修正）** |

### × 本作では使わない（1本）

| スクリプト | 理由 | 実走結果 |
|---|---|---|
| `gen_procedure_map.py` | 検査ではなく、tRPC の手続きと day の対応表を生成する道具。Supabase SDK 構成の本作に対応物が無い。出力先も `material/30days-curriculum/_meta/` | `[FATAL] router source dir not found: scripts/_server-routers` rc=2 |

### 自己テスト17本（B31 が言う「既知の陽性/陰性サンプル」の実体）

`python3 -m pytest` は **1件も収集しない**（rc=5）。17本に `def test_*` も
`unittest.TestCase` も無く、`main()` が自前でループする単体スクリプト形式だからである。
`check_quality.sh:229-247` も `python3 <file>` として1本ずつ呼んでいる。
**pytest を入れても解決しない。** 第三者パッケージへの依存はゼロで、
`requirements.txt` も `pyproject.toml` も要らない。

`python3 test_xxx.py` で1本ずつ走らせた結果は **11本合格・6本失敗**（合格分のケース総数 132 件）。
失敗6本のうち4本（`test_sale_package` / `test_check_tag_balance` /
`test_check_false_success` / `test_check_zip_reference`）は同じ `scripts/build-zip.sh` の欠落、
1本（`test_check_unused_image`）は `.github/workflows/material-gate.yml` の名前違い、
1本（`test_check_anchor`、21件中2件失敗）は本作に `src/app/page.tsx` が存在しないこと
による。内訳は `D14_検査スクリプトの実走結果.md` §1-3。

## 5. この棚卸しが露わにした、本作の設計の穴

`16_決定バックログ.md` へ B31〜B34 として起票した。

| # | 穴 | 根拠 |
|---|---|---|
| B31 | G0 の「道具4種」が前作の実績に対して貧しい | 本書 §0 |
| B32 | 教材のコードが lint を通るかの検査が無い | 前作 day09 の `dialogOpen` が Biome の `noUnusedVariables` で落ち、しかも FIXABLE のため `npm run fix` で消え、翌日 `is not defined` の手戻りになった。A8 はフォーマッタとリンタを決めているだけで、教材に載せるコードを実際に通す条項が無い |
| B33 | 貼り先ファイルの取り違えを誰も見ていない | 前作 day20 の `closeTaskDialog` が `router` を使うのに、`useRouter` の宣言は別ファイルへ貼る指示だった。貼った瞬間に止まる。本作の G5 は引用範囲の**内側**しか見ない（B29 と同じ層の穴） |
| B34 | `12_文体・AI臭さ排除方針.md` に「床/天井」が無い | 前作の `voice-spec.md` は、外部レビュー（阿部・杉田）の**「このままなら購入見送る」**という判定を受けて、売れた他教材3本（Python基礎／tkinter／Nomagram動画講座）と読み比べて下限と上限を言語化したもの。本作の 12 は「局長の既存TS教材が正本」までしか書いていない |

## 6. 前作の運用で、本作がまだ持っていないもの

| 運用 | 前作の実績 | 本作の状態 |
|---|---|---|
| クリーンルーム通し実行 | 教材テキストだけを読み `src/` を参照しない**独立オラクル**が Day01-10 / 11-20 / 21-30 を通した。全区間 BLOCKER ゼロ | **A5「G6実走の知識隔離」は、前作で既に実装され回っている。**本作の G6 が「共有フックが `npm install` を拒否する」で止まっているのは、運用の型をゼロから作ろうとしているため |
| blind-test | 教材の文が人に AI と見抜かれるかを6ラウンド測定。**限界を9項目自分で列挙している** | 本作の G3 は「禁止パターンを検出する」までで、検出をすり抜けた文が人にどう読まれるかは測っていない |
| 監査ログの書き方 | 「29件はまだ全件を現物で確かめていない。確認できたものだけを成立と書く」 | 本作の敵対レビュー台帳より厳しい |

## 7. 未処理として残すこと

- **`@textlint-ja/preset-ai-writing` の依存追加と、ルート `package.json` の要否**は
  B2（リポジトリ構造）と連動するため、ここでは設定ファイルのみ置いた。
  依存が入るまで、ルートの `.textlintrc.json` は不活性である
- ~~28本のスクリプトは**搬入しただけで、1本も実行していない**~~ →
  2026-08-06（D14）に28本＋テスト17本を実走し、§4 を測定値で書き直した。
  生の出力は `decisions/D14_検査スクリプトの実走結果.md`
- `check_anchor.py` の許可プレフィックスを何にするかは、Expo プロジェクトを1本
  作ってディレクトリ構成を実測するまで決められない（D14 §6）
- `check_quality.sh` の命名ガードの置き換え先は、D1-6 の `material/17_章分割表.md` と
  その読み取り口（`chapter_table.py`）が実在してから決める（D14 §6）
- 17本の検知テストを CI のどのジョブにどう並べるかは D13 と同時に決める。
  本書で確定できるのは「pytest は不要」「第三者依存はゼロ」
  「17本は `python3 <file>` で個別に呼ぶ」の3点まで（D14 §6）
