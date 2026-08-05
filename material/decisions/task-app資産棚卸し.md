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
| 検査スクリプト28本＋テスト17本 | `scripts/curriculum-qa/` | 無変更で搬入。**動く保証はまだ無い**（§4 の分類が済むまで実行しない） |
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

### ◎ 技術非依存。ほぼそのまま効く（15本）

| スクリプト | 何を見るか |
|---|---|
| `check_why.py` | コードブロックの直後に「なぜ」があるか。**外部レビューの「翻訳文感」の実体はここだったと前作が特定している** |
| `check_false_success.py` | 構造が閉じていない時点で「これでエラーが出なくなります」と書いていないか |
| `check_anchor.py` | コードブロックの書き込み先が、そのブロックだけ見て分かるか |
| `check_crossref.py` | 章間の参照先が実在するか |
| `check_step_ref.py` | 本文が指す Step 番号がその章に在るか |
| `check_step_time.py` | 所要時間の表の合計と本文の合計が合っているか |
| `check_step_length.py` | コードブロックが長すぎないか |
| `check_terms.py` | 同じ概念に2通りの書き方が混ざっていないか |
| `check_variants.py` | 同じ語の表記ゆれ（「すでに」46件に対し「既に」21件の混在を実測） |
| `check_tone.py` | 関西弁・タメ口・AI構文（**本作へ移植済みの1本**） |
| `check_comprehension.py` | 初心者向けの数値基準 |
| `check_visualization.py` | 表・図の量 |
| `check_no_skip.py` | ステップの連続性 |
| `check_code_completeness.py` | `filepath:` コメントの有無・分割禁止 |
| `check_unused_image.py` | 参照されていない画像 |

### ○ 手直しが要る（6本）

| スクリプト | 手直しの内容 |
|---|---|
| `check_ja_line_break.py` | JSX 内の日本語途中改行。**React Native でも同じ事故が起きる**が、判定対象の要素名が違う |
| `check_jsx_marker.py` | 同上 |
| `check_tag_balance.py` | 同上 |
| `check_tech_stack.py` | Next.js / shadcn/ui 前提 → Expo / React Native へ |
| `check_scaffold_curriculum_alignment.py` | scaffold の概念が本作に無い。A7 の章末スナップショットへ読み替え |
| `check_quality.sh` | 統合スクリプト。上記の結果を受けて配線し直す |

### △ 作り直しが要る（3本）

| スクリプト | 理由 |
|---|---|
| `check_zip_reference.py` / `check-sale-package.sh` / `sale_package.py` | **前作の30周目で見つかった最も重い1件**（本文8箇所が「リポジトリの `src/` と見比べて」と書いていたが、販売ZIPにその照合先が入っていない）に対応する道具。本作は配布が**3系統**（教材本文＝Drive／完成コード＝公開リポジトリ／章末スナップショット＝別配布）に分かれるため、前作の1系統前提では成立しない。**分岐が増えるぶん、前作より危険度は高い** |
| `check_procedure_order.py` | tRPC の手続き前提。Supabase SDK 呼び出しと RLS ポリシーへ読み替え |

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
- 28本のスクリプトは**搬入しただけで、1本も実行していない**。§4 の分類は
  docstring と前作の記録から導いたもので、本作での実走で確かめたものではない
