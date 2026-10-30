# 局長確認待ちの変更案: 文章スキルの共通節、writing-lint、恒久ルール、AGENTS.md の読み込み経路（2026-10-30）

状態: **局長確認待ち。どれも適用していない。**
`10_教材制作フロー.md`・`12_文体・AI臭さ排除方針.md`・`.claude/skills/material-writing/SKILL.md`・`AGENTS.md` は1文字も変えていない。

経緯: task-app を見本にした上位計画の Phase 1（文章スキルの更新）と Phase 2（CLAUDE.md → AGENTS.md）が task-app と redmine-clone で終わった。
sns-app では 10 と 12 が局長レビュー待ちのため、同じ変更を直接は入れず、ここに案として並べる。記録は `decisions/20261030-phase5-sns-app準備.md`。

局長に決めてもらうこと（4点）:

| # | 案 | 決めること | 受注側の推奨 |
|---|---|---|---|
| 1 | SKILL.md に task-app の共通節 v2 を取り込む | 取り込むか。取り込むなら 12 との優先関係 | 取り込む。12 を共通節より上に置く |
| 2 | writing-lint を G3 の候補ゲートにする | warn のまま参考にするか、gate にするか、採らないか | warn のまま参考。gate にするのは sns-app の本文で精度表を作った後 |
| 3 | 恒久ルール「教材は実コードを編集しながら、その場で書く」 | 10 と AGENTS.md に入れるか | 入れる。正本のコードは `listings/<章ID>/` と読み替える |
| 4 | AGENTS.md の読み込み経路 | 起動のしかたの前提を AGENTS.md に書くか | 書く。CLAUDE.md の shim は置かない |

---

## 1. SKILL.md に共通節 v2 を取り込む

### いまの状態

- sns-app の SKILL.md（398行）は、task-app から 2026-08-05 に無変更で搬入した版を手直ししたもの（`task-app資産棚卸し.md` §1）。
  共通節の印（`<!-- BEGIN common:material-writing v2 -->`）は無い。
- task-app の SKILL.md は、リポジトリごとの値の節と、3リポジトリで同じ文面の共通節に分かれた（task-app `SKILL.md:9-17,66,399`）。
  共通節の正本は task-app で、`scripts/sync-skill-common.sh` が写す。同期先の既定は redmine-clone だけで、
  sns-app は「局長判断待ちにしているため、承認されてから SKILL.md に印を入れ、DEFAULT_TARGETS に足す」と書かれている（同スクリプト `:14-15`）。
- vendor の差: sns-app の `hana652-tech-writing-pack/` は guides 01〜06 と `ai-smell-lint.py` だけ。task-app は上流 `780f29a` に置き換わり、
  guides 07〜10 と `writing-lint.py` がある。共通節は guide 07・08 と writing-lint を参照するので、取り込むなら vendor と `references/ATTRIBUTION.md` も同期する（sync スクリプトが一緒に写す）。

### 取り込む場合の手順（承認後）

1. sns-app の SKILL.md を「このリポジトリの値（sns-app）」の節と印つきの共通節に分ける。
2. task-app の `sync-skill-common.sh` の `DEFAULT_TARGETS` に sns-app を足し、sync を回してから `--check` で差分0を確かめる。（task-app 側の変更）
3. 共通節の外に、sns-app 固有の記録（下の値の表、12 との関係、textlint の採否）を置く。

### このリポジトリの値（sns-app）の下書き

| 項目 | 値 | 根拠 |
|---|---|---|
| 章数 | 未定（B1 の凍結待ち。18 は DRAFT で31章） | PROGRESS 09-23 |
| 教材の置き場 | `curriculum/<章ID>.md` | D1-1 |
| 正本のコード | `listings/<章ID>/`（章ごとの実プロジェクト。embedmd で引用する） | D1-5、10:343-359 |
| 1文の上限 | 100字（`.textlintrc.json` の `sentence-length`） | `.textlintrc.json:11`、`prototype-chapter/.textlintrc.json:4` |
| コードブロックの上限・段落 | 25行・3文 | 10:271（G3 構造チェック） |
| 文体 | 話者ラベルつき対話台本（`磯貝）`・`阿部）`） | 12 §1.1、16 A2 |
| writing-lint のモード | `warn`（下の §2 で決まるまで） | 本書 §2 |
| 冷えた読み手の通し読み | G6（知識隔離した実走） | 16 A5、10 §4 |

### 取り込むときにぶつかる所

- **文体の基調**: 共通節の「文体スペック」は、ですます体の地の文を前提に書かれている（task-app `SKILL.md:167-210`）。
  sns-app の 12 は「地の文は原則使わない。説明はすべて先生のセリフとして書く」（監査 D9 節が引く 12:20）。
  共通節の優先関係の表は「`material/**` では material-writing が唯一の権威」と書くが、sns-app で文体の正本は局長の既存 TS 教材から抽出した 12 である。
  そのため、sns-app の値の節に「文体は 12 が優先し、共通節の文体スペックは 12 と食い違わない範囲で使う」と書く必要がある。
- **対象のパス**: 共通節の文中の「material/**」は、sns-app では `curriculum/**` と読み替える（sns-app のフックの監視対象は `curriculum/**/*.md`、棚卸し §2）。
- **D10 との関係**: 監査 D10 の未処置分（スキルが 12 を参照しない）は、上の「12 が優先」を値の節に書けば閉じる。

---

## 2. writing-lint を候補ゲートにする

### いまの状態

- task-app の `scripts/curriculum-qa/run_writing_lint.py` は、上流 `writing-lint.py` を無改変で借り、出力を自分で判定するラッパー。
  モードは `gate`（失敗させる）と `warn`（表示するが rc=0）がある（同ファイル `:316,363`）。上位計画では `warn` を sns-app 用としている。
- sns-app の scripts・CI・hooks からは writing-lint も ai-smell-lint も呼ばれていない。

### sns-app の文章に当てた結果（2026-10-30、読み取りだけ）

`curriculum/` は本文0件なので、12 形式で書かれている候補 `prototype-chapter/candidates/d4-heavy/chapter-rls-denial-check.md` に当てた。

```text
python3 /home/user/task-app/scripts/curriculum-qa/run_writing_lint.py --mode warn <上のファイル>
→ rc=0。判定: FATAL 59 / DENSITY 未処置 0 / stale 0
同じファイルを --mode gate → rc=1
```

FATAL の59件は全部「禁止固有名詞『磯貝』（著者名（奥付以外））」で、どれも話者ラベルの `磯貝）` の行だった。
task-app のラッパーは `FORBIDDEN_NAMES` に `磯貝\s?光佑|磯貝` を持つ（`run_writing_lint.py:83-86`）。task-app では磯貝が著者名なので出荷物に出てはいけないが、
sns-app では先生役の登場人物名（16 A2）なので、12 に従って書いた章の発話行が全部 FATAL になる。

### 案

- 選択肢:
  - (a) warn のまま、G3 の NON-FORMAL の枠（`.github/ci/run.sh` の試作検査と同じ扱い）で参考に出す。
  - (b) gate にする。
  - (c) 採らない。
- 推奨: (a)。(b) にする前に2つ要る。1つは `FORBIDDEN_NAMES` をリポジトリごとの設定にし、sns-app では磯貝・阿部を外すこと（task-app 側の変更）。
  もう1つは、task-app と同じやり方で sns-app の本文に精度表を作ること（task-app `SKILL.md:250-279`）。task-app の上限は1日1万〜4万字の教材で決めたもので、対話台本の1発話272字以内の文に合うかは測っていない。
- 関係: B42（`check_tone.py` と prh のどちらを正本にするか）。writing-lint を入れると AI 典型構文の検出が3か所に分かれる。B42 と同時に決めるのが筋。
- 置き場: ラッパーは task-app の `scripts/` にあり、sync スクリプトは写さない。sns-app で CI から呼ぶなら、ラッパーを sns-app へ写すか、sync の対象に足す。

---

## 3. 恒久ルール「教材は実コードを編集しながら、その場で書く」

### ルール本文（task-app・redmine-clone と同じ）

> 1 Step は「作業ツリーの実コードを1か所変える → 動かして確かめる → その差分と理由を Step に書く」で1単位とする。
> 教材に載せるコードは作業ツリーの実ファイルから写し、手で打ち直さない。
> 後からまとめて書くことも、先に教材を書いてからコードを合わせることも禁止する。

（task-app `SKILL.md:68-79` の共通節の冒頭。上位計画 §3 のとおり、置き場は AGENTS.md の教材節と SKILL.md の冒頭の2か所）

### sns-app での読み替え

- 「作業ツリーの実コード」は `listings/<章ID>/`。sns-app は G5 で embedmd による引用を採っているので、教材のコードは既に実ファイルから機械で写される（10:343、G5 の突合は 10:227,257）。
  恒久ルールのうち「手で打ち直さない」は G5 が担保する。sns-app で新しく効くのは「先に教材を書いてからコードを合わせない」「Step ごとに、コードの変更と教材の変更を対にする」の部分である。
- G5 は引用範囲の内側しか見ない（16 B29）。範囲の外でコードが変わっても教材は緑のまま、という穴は B29 の判断に残る。

### 入れる場所の案（承認後）

| 場所 | 入れる内容 |
|---|---|
| `AGENTS.md` | 「教材」の節を新設し、ルール本文と、正本のコードが `listings/<章ID>/` であることを書く。今の AGENTS.md は GitHub Project の節だけ |
| `10_教材制作フロー.md` | `listings/<章ID>/` を定める箇所（10:343-359）の隣に、ルール本文と、G5 が担保する部分・担保しない部分（上の読み替え） |
| SKILL.md | §1 の共通節の取り込みで入る（共通節の冒頭にある） |

---

## 4. AGENTS.md の読み込み経路

### 実測（2026-10-30、Claude Code 2.1.314）

sns-app の AGENTS.md の末尾に一時的に `CANARY: SNS-AGENTS-7731` を足し（commit していない。測った後に `git checkout -- AGENTS.md` で戻した）、
`claude -p "<CANARY: で始まる行をツールを使わず答えよ>" --max-turns 1` で確かめた。

| 起動のしかた | 結果 |
|---|---|
| cwd=/home/user/sns-app | 読まれた（`CANARY: SNS-AGENTS-7731` を回答） |
| cwd=/home/user（親ディレクトリ） | 読まれない（NONE） |
| `--add-dir /home/user/sns-app`（cwd=/tmp） | 読まれない |
| `--add-dir` ＋ `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` | 読まれない |

redmine-clone の実測（`/home/user/redmine-clone/material/_meta/agents-canary.md`）と同じ結果である。一次ドキュメントは https://code.claude.com/docs/en/memory （2026-10-30 取得、同記録が引用）。

### 案

- sns-app は CLAUDE.md が無く、AGENTS.md だけ。cwd=リポジトリで起動すれば読まれる。
- task-app で試した `@AGENTS.md` の1行 shim は、`--add-dir` の経路を救わなかった（同記録の追記）。sns-app に shim を置いても得るものが無い。
- 推奨: shim は置かない。AGENTS.md の冒頭に「sns-app の作業は cwd=/home/user/sns-app で起動したセッションで行う」と書く。
  教材の執筆を自動化するとき（Workflow や別セッション）は、起動条件にも同じ前提を入れる。
- 決めること: この前提を AGENTS.md に書いてよいか。AGENTS.md は Copilot・Codex など他の道具も読むので、Claude Code 固有の注記として書くかどうかも含む。

---

## 承認後にやること（順番）

1. §1 の取り込み（SKILL.md の分割、sync の同期先追加、vendor の同期）。
2. §3 の恒久ルールを AGENTS.md・10 へ。
3. §4 の起動前提を AGENTS.md へ。
4. §2 は、`FORBIDDEN_NAMES` のリポジトリ別設定と、sns-app の本文での精度表ができてから gate 化を判断する。それまでは warn。
