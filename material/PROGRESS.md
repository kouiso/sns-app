# 進捗台帳（常にこのファイルが最新の正）

最終更新: 2026-07-30 / フェーズ: **Phase 0 計画固め**（`14_マスターロードマップ.md`）

## 2026-07-26 の構成振り直し（Capacitor + NestJS → Expo + Supabase）

局長決定により技術構成を振り直した。実装コードは1行も存在しないため移行コストはゼロ。
経緯と比較検討は `02_技術選定書.md` §2・§3 が正本。

| 書き直した文書 | 主な変更 |
|---|---|
| 02 技術選定書 | 全面書き直し。Expo vs Capacitor / Supabase vs NestJS構成の比較、既知の限界5件 |
| 00 企画概要 | 「サーバーまで全部自分で作れる」を撤回し、サーバー学習はシリーズ全体で満たす形に |
| 01 要件定義書 | FR1→Supabase Auth / FR9→Realtime / **FR13・FR14・FR15 を追記（再承認が必要）** / 非機能セキュリティを RLS 中心へ |
| 03 基本設計書 | 構成図差し替え。画面 12→15。UC3（メール確認とディープリンク）新設 |
| 05 DB設計書 | refresh_tokens 削除 / users を auth.users と1対1に / **RLS の節を新設** |
| 09 シリーズロードマップ | 第2弾＝別スタックWeb版、第3弾＝NestJS を正式化。ボツ案を捨てずに移設 |
| 11 ペルソナ・UX | 体験マイルストーンの順序を入れ替え（スマホが最序盤・Web が最終ハイライト） |
| 14 マスターロードマップ | Phase 2 の道具を「既製品4種＋自作2種」に改訂。OpenAPI照合コンパレータ消滅 |
| 15 カリキュラム骨子 | パート構成を作り直し。**章数目安は捨て試作の実測まで空欄** |
| 16 決定バックログ | B群を書き直し（消滅2 / 書き直し5 / 新設2）。C3〜C6 の局長回答を記録 |

**未着手**: 04 / 06 / 07 / 08 / 10 / 12 / 13（10・12・13 は技術非依存のため全面生存）。
**次にやること**: Codex Round 12 残りの裏取りを継続し、03・05 へ Realtime publication / React Native セッションライフサイクルを詳細化 → 局長の Phase 0 文書レビュー → 捨て試作。

## Phase 0: 文書の状態

| 文書 | 状態 | 備考 |
|---|---|---|
| 00_企画概要 | ドラフト・局長レビュー待ち | |
| 01_要件定義書 | ドラフト・局長レビュー待ち | 前提を「単体でも始められる」に改訂済み（2026-07-24局長決定）。**Round 12 反映**: パフォーマンス200ms目安を見直し中、FR9にRealtime再取得、FR1にReact Nativeセッションライフサイクル、前提にExpo Go/development buildの注意を追記 |
| 02_技術選定書 | ドラフト・局長レビュー待ち | **Expo (React Native) + Supabase**（2026-07-26局長決定で振り直し）。**Round 12 反映**: 既知の限界に R6 SDK版/Expo Goの食い違い、R7 development buildの必要性を追加。未決定事項に B16・B17・B18 を追加 |
| 03_基本設計書 | ドラフト・局長レビュー待ち | **Round 12 反映**: UC1/UC2にRealtime再取得、UC3にdevelopment buildの必要性、SupabaseクライアントのReact Nativeライフサイクルを補足 |
| 04_詳細設計書 | 未着手（Phase 1）→ ドラフト先行版 | 着手条件: 03承認。**Round 12 反映**: 目次に deep link/development build、Realtime publication/再取得、RLS 列単位権限、SDK 版選択を追加。**03 承認前の仮案として 7 画面の詳細設計とセクション 2-7 を追加** |
| 05_DB設計書 | ドラフト・局長レビュー待ち | **Round 12 反映**: RLS節にキー取り違え防止、UUID/created_atのDB default追加、Realtime publication設定を新設 |
| 06_API設計書 | 未着手（Phase 1）→ ドラフト先行版 | 着手条件: 03+05承認。**Round 12 反映**: 目次に DB default、RLS 列単位権限、`auth.users` トリガー、Realtime 再取得、Storage bucket 制限、API キー契約を追加。**03/05 承認前の仮案として RLS SQL・トリガー・Realtime publication の先行記述を追加** |
| 07_開発スケジュール | ドラフト・局長レビュー待ち | **Round 12 反映**: 実装フェーズ引き継ぎ条件に Expo SDK 版/development build、Storage bucket 制限、カスタム SMTP 捨て試作を追加 |
| 08_テスト計画書 | 未着手（Phase 1） | 着手条件: 04+06確定。**Round 12 反映**: 目次の200ms測定条件を「DB側EXPLAIN ANALYZEとクライアント体感時間の分離」へ見直し。実機確認手順に SDK 版/development build を追加 |
| 09_教材シリーズロードマップ | ドラフト・局長レビュー待ち | |
| 10_教材制作フロー | ドラフト・局長レビュー待ち | 手戻り16件対応表 |
| 11_ターゲット・ペルソナ・UX定義 | ドラフト・局長レビュー待ち | 売り物兼社内用・単体開始OK反映済み |
| 12_文体・AI臭さ排除方針 | ドラフト・局長レビュー待ち | 局長の既存TS基礎教材（Drive）から文体スペック抽出済み |
| 13_記録・進捗管理規約 | ドラフト・局長レビュー待ち | |
| 14_マスターロードマップ | ドラフト・局長レビュー待ち | |
| 15_カリキュラム骨子案 | ドラフト・局長レビュー待ち | パートA0〜E構成・体験ゴール・退屈対策（2026-07-24追加）。**Round 12 反映**: パートA0体験ゴールにExpo Go/SDK版の注意を追記 |
| 16_決定バックログ | ドラフト・局長レビュー待ち | **未決定事項の唯一の正本**。A群10件確定 / B群に B17〜B22 を追加し一次資料裏取り済みで更新（2026-07-30）/ C群6件が局長判断（2026-07-25追加） |

## 質問バッチの回答（2026-07-24 局長回答済み）

| # | 質問 | 回答・反映先 |
|---|---|---|
| 1 | 登場人物名 | いったん磯貝/阿部のまま（後で一括置換可能な設計にした） → 12 §4 |
| 2 | Drive教材の扱い | 取り込みではなく**スタイルの正本**（「一緒に進めてる感」の再現が目的） → 11 §3, 12 §4 を訂正済み（14は伴走フェーズ再編で該当記述を11/12へ集約） |
| 3 | 教材の長さ | 長くなるのは可。禁止は「つまらない/つながり不明/セキュリティガチガチ」 → 11に退屈・迷子防止原則4〜7を追加、15の骨子に反映 |
| 4 | edu-creator改修着手 | 実装は**全面停止中**（局長指示: 作業一切禁止・計画作り込みに専念）。改修内容の説明は済み、着手は局長のGOが出てから |

## 敵対レビュー状態

- Codex Round 1（2026-07-24）: CRITICAL 3 / MAJOR 23 / MINOR 6 → 全32件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round1.md`。反駁0件・修正23件・Phase 1文書へ移記9件）
- Codex Round 2（2026-07-24）: CRITICAL 2 / MAJOR 12 / MINOR 6 → 全20件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round2.md`。R1の32件中25件は解消済みと認定された）
- Codex Round 3（2026-07-24）: CRITICAL 2 / MAJOR 8 / MINOR 6 → 全16件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round3.md`。収束: 32→20→16件）
- Codex Round 4（2026-07-24）: CRITICAL 1 / MAJOR 7 / MINOR 1 → 全9件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round4.md`。収束: 32→20→16→9件）
- Codex Round 5（2026-07-24）: CRITICAL 0 / MAJOR 4 / MINOR 1 → 全5件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round5.md`。収束: 32→20→16→9→5件、CRITICALゼロ到達）
- Codex Round 6（2026-07-24）: CRITICAL 0 / MAJOR 3 / MINOR 0 → 全3件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round6.md`。収束: 32→20→16→9→5→3件）
- Codex Round 7（2026-07-24）: CRITICAL 0 / MAJOR 1 / MINOR 2 → 全3件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round7.md`。残りは表記整合のみまで収束）
- Codex Round 8（2026-07-24）: CRITICAL 0 / MAJOR 3 / MINOR 0 → 全3件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round8.md`。ゲート迂回系の抜け道3件を封止）
- Codex Round 9（2026-07-24）: CRITICAL 0 / MAJOR 3 / MINOR 0 → 全3件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round9.md`）
- Codex Round 10（2026-07-24）: CRITICAL 0 / MAJOR 1 / MINOR 1 → 全2件を処置し文書へ反映済み
  （処置台帳: `material/reviews/codex-round10.md`）
- Codex Round 11（2026-07-24）: **CRITICAL 0 / MAJOR 0 / MINOR 1 → CONSENSUS-READY: YES（合意成立）**
  残MINOR 1件も同ラウンドで修正済み（台帳: `material/reviews/codex-round11.md`）。
  全11ラウンド・計92指摘を処置（反駁0件）。
- **Codex Round 12（2026-07-27〜30）: スタック変更差分の別ファミリーレビュー。CRITICAL 7 / MAJOR 4 / MINOR 2 → 全13件を裏取り開始。3件は即 05_DB設計書 / 09_教材シリーズロードマップへ反映、6件（B17〜B22）は `16_決定バックログ.md` に起票し一次資料で裏取り済み、残りを 01/02/03/05/08/15 へ反映。次は局長のPhase 0文書レビュー → 捨て試作**
  （台帳: `material/reviews/codex-round12-stack-pivot.md`。一次資料: Expo docs / Supabase docs 2026-07-29 確認）

## 関連リポジトリの作業状態

- task-app/edu-creator: `GENERICIZATION_PLAN.md` を `docs/edu-creator-generalization-plan` ブランチにコミット済み（局長の未コミット作業には未接触）
