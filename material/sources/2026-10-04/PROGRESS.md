## 2026-10-04 — SNS設計の採否入口を集約

全体v7/API補足/B回復補足を3版に区別し、原契約変更/原同期/レビュー範囲/必要実測/正式採否receiptへ一つの入口を作成。84ID・114原行・DB13全13・原31章を照合。候補選択null、原採用/全三者/実測/実装可能はfalse。decisions/20261004-SNS設計の採否入口.md参照。

## 2026-10-04 — known-key入力喪失の回復比較（未採用）

現方式停止/既知keyの本人明示閉鎖/登録保存dispatch統合を比較。第一比較の閉鎖案は元WREC変更が必要。保持・旧writer・濫用のnative3指摘を修正し最後3修正限定0。原正本3資料のhash維持、三者/実測/原採用false、key喪失は未解決。whole-design/registration-loss-recovery-manifest.json参照。

## 2026-10-04 — 保存・復帰APIの具体案（未採用）

6論理操作・権限・排他・固定入力・画像保持・ackを比較案へ具体化。nativeレビュー5→3→最後3修正限定0。登録不明/入力喪失/server不存在の安全回復は未設計で、新保存停止の限界を記録。原採用/実装可能/実測/三者合意はfalse。whole-design/save-api-candidate-manifest.json参照。

## 2026-10-04 — v7原反映の準備・旧最新レビュー表示の訂正

v7原反映6対象を原hash/アンカーへ束縛し、Auth/D4/G6の開始条件をwhole-design/original-v7-adoption-deltas.mdへ保存。entry-screen-designの旧v20合意は現行版と異なるためlatest表示を訂正、履歴保存。11文書照合PASS。原反映/実測/実装開始/正式承認/全目標完了はいずれも未成立。

# 進捗台帳（常にこのファイルが最新の正）

## 2026-10-04 JST: 候補v7内の分岐同期と、外部レビュー未成立

- 前ターンはprogress（保存前確認補足・具体差分・実三者証拠）。5差分をmaster/画面JSON/native/whole/DESIGNの候補へ反映。原04等は未適用。6復帰画面の独立copyもcanonicalへ揃えた。
- 実同期v7 Gemini0/Opus2/GPT4、r2 Gemini0/Opus2/GPT2を照合し修正。AUTH12 transport、無入力normal入口、R1結果優先、nativeglobal境界、terminalguard誤付加/漏れ、新保存入口のgate不足を閉じた。旧0をcurrent合意へ流用しない。
- 新key admission/予約のserver原子性と全writer統一をWREC追加採用条件にした。native r3のpre-input予約矛盾を最小案Aで修正し、navigationは予約なし、submitで入力freezeして予約を一度確認、その後same-key保存へ。最終予約phaseはnative限定必須0。
- Droid r3は両terminal exit1/raw空。Claude weekly402、4日後reset。Gemini CLIはPATHなし、Claude CLIは未認証とread-only診断。追加課金なし。current最終Gemini/Claudeレビューは未成立。latest-candidate-sync-review.jsonで明記。
- 16の文書/hash/row確認PASS。runtime/UX/SQL/G6未実測、全12要件未完、goal active。B32希望async質問は未回答で承認/実測扱いなし。アプリ/newvalidator/build/SSH/実機/DB/cloud/mail/公開は進めていない。

## 2026-10-04 JST: 保存前確認・非採用比較・未適用分岐差分

- 前ターンはprogress（全体案提出と実三者最終修正証拠）。今回は設計補足のみ。保存前登録不明の端末限定案内、同操作続行、別端末/再起動/履歴喪失の結果確認、WREC非採用の保証差、R01-R08候補を具体化。
- 補足v1実Gemini0/Opus2/GPT1。端末内未dispatchを全経路未開始へ広げた誤案内、旧復帰分岐で登録不明が未送信へ漏れる経路、旧POST02/AUTH04のterminal不足を発見。文言とlock確認を修正し、5行の未適用分岐置換・同期差分へ記録。
- v2は三者補足限定必須0、8入力hash/receiptを確認。旧coreは変更せず同期前と明記。包括規則だけで旧行修復済みとしない。原採用/原同期/実測/実装開始/全12要件完了は未達のまま。
- 有効な任意を保持し、成功後の現在値を旧保存値と同一扱いする追加文言は採用しない。アプリ/新validator/build/SSH/実機/DB/cloud/mail/公開は進めていない。goal active。

## 2026-10-04 JST: 読める全体設計案v6と最終修正の提出

- 商品/学習サイクル/原31＋145候補のB32/段階的4入口/7出口/基礎26＋追加3/保持・中断再開/採用条件/全12要件を一つの正本と個人閲覧用一時HTMLへまとめた。実装を固めてから進めるユーザー指示を維持。
- 全体レビューを6版反復。結果の不一致を原rawで照合し、WRECのpost/profile別予約・排他的terminal・拒否/中止理由・元入力不在の中止・正常本人履歴・成功と現在値read分離・条件付き保持を具体化。原採用済み/実装済みにはしない。
- 全体v6はGemini0/GPT0/Opus1。master表2行の古い成功read条件を修正し、実Droid Gemini3.8Flash/Opus5.5 mediumと独立GPTで限定必須0。全体再レビュー0/100点保証とは扱わない。latest-external-review.jsonでscope/hash/terminal receiptsを保存。
- 24source、84未採用判断、DB13/FR15、26＋3、7出口、全12要件等の12静的確認がPASS。runtime/UX/G6未検証。任意の設計注記、原採否/同期/承認、実測は残る。implementation_ready=false、goal active。
- アプリ/newvalidator/build/SSH/実機/DB/cloud/mail/公開は進めていない。以前の追加事項・旧code・Phase0承認・C7/C8未回答を保持し、提出と全goal完了を分けた。

## 2026-10-04 JST: 全体設計v2の取りまとめと三者の反論照合

- 直前の終了見込み回答はstatus-only/no-progress。現行原資料と実v1 raw/receiptを再確認し、master冒頭に商品・原31章/B32・4入口・章別導入・7中断出口・保持/logout/診断・原差分の全体案をまとめた。今回は文書/JSONの設計修正であり、アプリや新検証codeを実装していない。
- 実v1 Geminiは必須0、Opusは必須7、独立GPTはpreUID契約の必須1。Geminiの0は見落しがあり全体合意としない。M1/M2/M4/M5/M6/M7を一括修正。M3の新key再開はOP-13の保証差があるため第一候補へ採用せず比較代案のみ。未知結果は未知のまま、server正常owner履歴再構成/照合を採用・実測gateにした。
- 基礎26状態と追加2候補を分け、RESULT-01の条件付き遷移/settleとRESUME-01文言・guardを具体化。native/Web/画像/UID前Auth記録を区別。iOS44pt/Android48dp/Web比較、120B86診断とread≠UPDATE、原主体/P1G1期限/導入章/同期/全工数の未採番候補表を追加。
- 原31/84判断/DB13全13/FR15/24sourceの保持を作者の静的確認で照合。これはruntime/UX/SQL/G6/全goalの証拠ではない。全体v2は32凍結入力で実Droid Gemini/Opus5.5 mediumと独立GPTに再レビュー依頼中。結果はterminal receiptを読んでから記録する。
- 全12要件、C7/C8、原採用/同期/正式承認/必要実測を保持。implementation_ready=false、goalはactive。設計先行のためbuild/SSH/実機/cloud/mail/公開を進めない。


最終更新: 2026-10-04 / フェーズ: **Phase 1 詳細設計**（`14_マスターロードマップ.md`）

## 2026-10-04 JST: Auth資源と受入条件の同一版接続

- 既存設計判断パッケージへ追加節。S1〜S5/SIGN8、A/B/peer準備、mail ledger、確認/reset、費用・責任・期限を凍結bindingとrun/stageへ接続。実資源/route/runは空の設計契約。
- 原H7のPCブラウザ/元アプリ待機とB103回復、原H8のnative deeplink画面・3端末枝/元スマホ新credential login、B88全insert/update/03,06,08整合、B95更新とAuth購読を別証拠にした。event目的/件数/retry/順序と全event集合を事前計画へ照合し、unknownや計画外をPASSへ混ぜない。
- 実Droid Gemini 3.8 Flash/Opus 5.5 medium第5回と独立GPTは同一現在版に追加節限定必須0。失われた旧実行は空raw/欠落handleとして保存し、現行合意に用いない。receipt/hash/範囲はauth-resource-binding/latest-external-review.json。
- 13source/27凍結inputのhash等を静的確認しただけで、原採否/実Auth/D4G6/全QA/P1G1/実UX/全goalは未完。設計を固めるまで実装/new検証code/build/実機/SSH/cloud/送信/公開へ進めない。次は残る画面guard・離脱/再開と31章の入口/終点をつなぐ。

## 2026-10-04 JST: メール需要と相手役準備

- 原19項の宛先/用途と13suite/6準備種を接続。要求開始状態と実送信/消費/到達/リンク、準備instance、費用/実作業/待機を分け、共有準備・rolling窓の重複と未帰属/未知網羅性を保持する。
- 独立GPT初回3、実Opus初回3/第2回1、独立GPT残文1/2を修正。Droid実Gemini 3.8 Flash/Opus 5.5 medium第3回と独立GPTは同一現在版に限定必須0。版/hash/receiptはmail-demand/latest-external-review.json。モデル読了は自己申告でOS監査ではない。
- 原採用前条件§3のcharged確定/集計式改訂も明示候補差分、原担当採用待ち。所有宛先/SMTP/枠/N1〜N5/実Auth/費用/人間独学/原同期/P1G1は未完。台帳案を全goal完了へ狭めず、実装/build/実機/cloud/送信/公開を進めない。

## 2026-10-04 JST: 学習の連続性と画面・データ条件

- 独立GPTで旧設計に5停止点（B生成/次章資源消失/120早期timeline/skip再開/理解判断）を発見し、未採用比較案として具体化。学習者L3/L6と局長C8は別。再レビューは限定必須0で実UXや設計全体完成を証明しない。
- DB13全13とFR1〜15を原文/判断/必要証拠のまま章・画面へ接続。導入と前提/後続を分け、130画像/200通知/170 timelineを前倒ししない。静的JSON/hash/参照確認のみ。120候補firstを保存値確認に修正し、原firstと修正前レビュー対象版を保存。
- Droid実Gemini 3.8 Flash/Opus 5.5 medium第5回と独立GPTは、同一版の学習連続性/DB13/FR接続に限り必須0。章単位G6と本人の160→170持越し証拠を分ける。raw/receipt/hash/限定範囲はlearning-continuity/latest-external-review.json。原採用/実測/全原同期/Auth/D4G6/QA/P1G1は未完、実装/build/実機/cloud/公開は進めない。

## 2026-10-04 JST: 章境界の開始・終了・復帰比較

- 原31章の開始資源/最初の成果/終了状態/復帰を章境界比較案へ対応。A31/B32/C32/D33を110分割と145分離の二軸で保持。原31 ID・順序・原終了文・前章鎖・source hashを作者が静的確認した。
- 原04依存nodeとFR、原終了文と候補要約、判断IDと変更対象文書/節/行を区別。一覧read失敗は保存結果不明へ読み替えない。Phase0 20260806承認を維持。
- 未採用・未測定・NON-G1。実snapshot/真正未着手/比較実測/全原同期/正式G1は未完、implementation_ready=false。設計を固めるまで実装・新検証コード・build・実機・cloud・公開は進めない。独立GPT必須1（150の原未決と候補混在）を修正し、再レビューで限定必須0。全31原未決IDを独立照合。根拠はchapter-boundaries/independent-review.md。

## 2026-10-04 JST: 登録・初投稿・復帰の画面文言と章別遷移

- 現行3journey/26状態は未採用の設計案。送信前/開始済み結果不明、保存確定/確定拒否/対象利用不可、本人・用途・章別入口を分離。原140論理削除/260camera保持。
- Droid実Gemini 3.8 Flash/Opus 5.5 medium第1〜20回のraw/receipt/input snapshot保存。現行26状態の文言/guardに限り三者必須0・限定合意。限定範囲はlatest-external-review.json。
- AUTH08/16継続確認不可の離脱/logout、AUTH11未成立離脱、AUTH14権限拒否後、B14/B88再開、POST03/04照合未成立後の新規作成、R1等対象利用不可の結果表示/再開、OP/RET保持/破棄は未完。
- 26一意/参照欠落0/共通列/原5入力不変を静的確認。private HTMLは仮データの設計レビュー、JS構文のみで実UX未測定。アプリコード/送信/DB/build/実機/cloud/公開は進めない。教材設計を固めるまでimplementation_ready=false。原Auth/D4G6/QA/C7C8/P1G1全goal保持。次は原31章・全画面・DB13を通し学習体験で照合する。

## 2026-10-04 JST: Auth署名とWindows/iPhone学習者資源の公式照合

- 採用前条件へ新§13追加。5経路のcloud build/device install/講師ad hoc UDID運用/無料Mac Personal Team期限/Expo Go scheme/狭い代替を分離。原B-P0のpaid登録禁止は初心者QR退路の文脈で保持し全制作課金禁止へ拡張しない。主Mac/Windows対象未決、講師一台成功と購入者独立、JS reload/native変更時再buildを区別。
- Expo/Apple公式仕様読取で実team/SDK57/EAS plan/端末は未測定。SIGN8 native/JSON、原8入力hash不変、前native snapshot/prefix、現行SHA一致。新§13限定GPT必須0、旧レビュー/packet旧SHAへ追加節の合意を外挿しない。前後版とreview範囲をauth-signing-designへ保存。
- 原採用/全SQL同期/実装/新検証コード/build/SSH実機/cloud/公開なし。必要な費用/開始資源/期限後復帰/全Auth受入は未完。最新Gemini/Opus本案合意なし、C7C8未回答とAuth/D4G6/QA/P1G1全goalを保持。

## 2026-10-04 JST: 論理削除と保存確認記録の保持比較

- 原01 FR3/05§3/06の論理削除と照合し、同じ設計案へR1正確入力保持、R2削除時の終了/比較入力除去、R3 TTL忘却不適合を追加。R2は次の優先比較で未選択。owner/keyを占有し続け全同key再作成を拒否、入力一致は確認せず本人の最小終了結果。元posts/Storage/通知/backup完全消去を意味しない。
- R2条件付きRET6と元OP18のnative/JSON一致、原11入力hash不変。追加節の独立GPT必須0、前版レビューは別保存。全削除入口/同transaction/lock順/保守移行/保持期間・容量/140260概念負荷は未採用未実測。元OP18の実走/合格数へ追加しない。
- 原台帳/全SQL同期、実装/新検証コード/build/端末/cloud/公開なし。直近の外部枠エラーから新しい回答を得たとは扱わず、最新本案三者合意なし。C7C8未回答とAuth/D4G6/QA/P1G1全goalを保持、implementation_ready=false。

## 2026-10-04 JST: 投稿返答喪失の操作照合・権限・保持と教材負荷の比較

- 設計のみ。入力保持/本人の結果確認/同key再試行、owner+keyと正確な受理入力、成功receiptとDB全transaction、A用途限定writer/B全経路制約/C既知IDを比較。VOLATILE/READ COMMITTED/lock後別SQL/同outer transaction、B即時一意性と別遅延終了形を公式仕様へ照合。実project版/権限/接続/挙動は未測定。
- OP18件のnative/JSON一致、原11入力SHA不変。独立GPT静的敵対レビュー必須0、対象4SHAへ束縛。receipt保持/本文残存/purge/版、Storage別境界、初投稿章の概念量/B50/D4負荷は採用前条件。原16へ未採番起票候補で原採番や採用を代替しない。
- 原SQL/migration/原本文同期patch、アプリ/新検証コード/build/実機/cloud/公開なし。最新Gemini/Opus本案合意未成立、C7C8未回答、Auth/D4G6/QA/P1G1全goal保持。freeze/implementation_ready=false。

## 2026-10-04 JST: 設計判断を6束へ統合、原Phase0承認と後続未達を分離

- 設計判断packetで商品/学習体験、32章比較、Auth/投稿/全画面/独学資源/正式評価を束ね、原31/84/DB13/全goalを保持。原承認パッケージの2026-08-06 Phase0承認記載とPhase1着手を確認し、現行01再承認/P1G1と分離。原14旧表示/画面数/PDF既決の未適用同期差分を一時適用して候補hash再現。
- 原offlineは壊れない範囲でqueue追加なし。原84台帳文/章依存集合一致と全未採用、27入力hash一致。保存QA6件のテストファイル/raw現在一致は再実行/対象本体全imports/実教材の証明ではない。保存Auth controlled/外部メールfalse、最新外部相互合意なしを保持。
- C7場所/C8節目は原16に基づく具体候補の質問を提示、回答nullのまま。既定選択/無回答を採用/公開/実審査にしない。独立GPT判断束/14差分とQA範囲再検査とも限定必須0。実装/本文/新検証コード/build/端末/cloud/公開なし、全goal active。

## 2026-10-04 JST: 全画面の入口/復帰と34移動条件、原3資料の統合部分候補

- 設計のみ。原04表全16行（画面総数ではない）の入口/通常出口/失敗復帰/本人保持/章境界を具体化。34件の条件付き移動を原名へ束縛し、完成SNS入口と途中章を分離。通知type/不整合ID、本人bookmark、camera取消、Auth用途、履歴なし/直接URL/logout不明を保持。
- 独立GPT全16行/追加34条件とも限定必須0。原名/FR/状態/未決とnative JSON一致、全行/edge未採用・未測定/未実走、条件付き静的到達を確認。静的到達はguard実装や利用者完走ではない。
- evidence/20261004-navigation-design: 先の6状態候補＋08の31章課題追記＋全画面/移動を04/06/08統合未適用部分差分へ。原source/上流candidate hash一致、3候補を一時適用しhash再現。合成はroot静的検証で独立全SQL同期/原承認/実走/最新三者合意ではない。全goal保持、実装/build/端末/cloud/公開なし、freeze/implementation_ready=false。

## 2026-10-04 JST: 原31章の変更・説明・復帰課題と原4資料の部分差分

- 設計のみ。原31章へ概念導入後の課題・本人説明・開始資源/復帰を個別割当。原ID/順序/前章/最初の結果/未決依存を保持。11/12/18/08の未適用部分差分を作成し、4source不変・一時適用候補hash再現・JSON/native31行一致を確認。
- rootのsession前提照合で100/110/120の管理観測/通常権限対照時点を未採用原同期案へ修正。独立GPT指摘の160自己follow採否、210追加D用途/準備/送信需要も同期し限定再検査必須0。原正負受入を削除せず、users read期待は公開read採否へ接続。
- 課題/別掲解答/本文完成、受講者理解・実走・正式G6・原承認・最新Gemini/Claude合意は未完。元8段階案への接続追記は以前のレビュー範囲外として記録。145/110比較・全84/DB13・Auth/D4G6/QA/C7C8/P1G1を保持、実装/build/実機/cloud/公開なし、goal active。

## 2026-10-04 JST: 学習体験と修了判断の設計候補

- 最新設計先行指示に沿い、原31章を8段階へ接続。写経から本人の判断へ進める予想/変更/現物確認/説明/復帰課題を具体化し、FR1〜15を保持。支給/自作、環境成立/理解、解答参照/自力判断を区別する候補。合格点や新時間閾値は追加しない。
- 独立GPT必須2→修正再検査0。原12の概念導入順と原キーボード/コントラスト比を維持。読み上げ/拡大/記録手段は追加比較候補で原承認前に修了条件へ必須化しない。外部Gemini/Claudeの最新案レビュー・受講者理解・正式G6・原承認は未達。
- evidence/20261004-learning-outcomes: 原5資料hash不変、31章の段階対応が重複欠落なし、全FR明記と候補SHAを記録。静的対応のみで理解や体験成立の証明ではない。DESIGNに索引追加。実装/本文/新検証コード/build/実機/cloud/公開なし、Auth/D4G6/QA/C7C8/P1G1を保持しgoal active。

## 2026-10-04 JST / 2026-10-03 18:15 UTC: 主要画面状態と04/06/08本文候補

- 設計のみ。6グループの正常/失敗/入力保持/API/受入/保留を全DB13へ対応。04共通S2/投稿順序差替、06操作/受領世代、08正負状態の未適用本文候補3本。6は画面総数でなく全IA/旧SQL完全同期は未完。
- 独立GPT必須3→1→0。生password/URL tokenとSDK session保存を区別し、B19DB生成UUIDだけでは応答喪失を照合できないことと別採用operation契約を明記。auth/request/query/cursor世代と更新trigger、追加page直列/refresh旧page、逆順受入をJSON共通欄にも同期。外部三者/実測/原承認は未証明、Droid追加呼出なし。
- evidence/20261004-screen-contracts: 原source hash不変、全DB13参照、6entries/共通3契約nativeとJSON一致、未適用3patchを一時適用し候補hash再現。原masterへ適用せずアプリ/fixture/新検証code/build/端末/cloud/公開へ進めない。Auth/D4G6/QA/C7C8/P1G1保持、goal active、freeze/implementation_ready=false。

## 2026-10-04 JST / 2026-10-03 18:05 UTC: 原DB13の画面/API/受入契約

- 設計のみ。原05§4の13番号/原文に完全対応した契約packetを作成。学習者結果、原04/05/06/08同時変更候補、原主体/期限、正負証拠、プレモーテム保留条件。全13未採用、原未決を保持。
- 独立GPT初回必須2→修正再検査0。画像の全成功/全rollback/並行他人SELECTで途中形不可視/UPDATE DELETE終了形、通知取消で旧履歴保持・成功再作成1件追加/失敗増分0・本人既読旧時刻保持・他人read_at更新削除拒否を具体化。外部三者合意/実測/100点は未証明。Droid追加呼出なし。
- evidence/20261004-db13-sync: source hash不変、13原文/番号/JSONとMD契約欄一致、依存は原84内、05索引追記の未適用部分patchを一時適用し候補hash再現。全table/04/06/08本文の正式同期ではない。アプリ/fixture/新検証code/build/端末/cloud/公開を進めずgoal active、freeze/implementation_ready=false。

## 2026-10-04 JST / 2026-10-03 17:53 UTC: 全84採用提案・独学復帰・開始条件

- 設計のみ。3分冊各28の第一候補/代案/同時条件/原変更候補/未測定承認を84索引へ接続。推奨体験と採用前条件、対応版/中断再開の案を具体化。構成A31/B32/C32/D33の二軸、B第一評価で未凍結。原16baseline不変、全件未採用・原同期未適用。
- 既存QA歴史的6FAIL対応selftestsを現行sourceで再実行し6/6PASS。source/raw SHA保存、実教材/PDF・全QA・正式G3/G6へ外挿しない。旧FAIL/未判定を保持。
- 実Droid Gemini3.8Flash/Opus5.5 medium 14試行12成功2空raw失敗。GPTが初回/相互批判を照合し修正。最後の有効v6はGemini必須0/Opus必須1（D4時点）。v7はrequest error/Core usage limitで意見なし。以降の修正版外部相互合意は未証明。購入/公開せず、原D4と原10の実読でG1前教材外本番書式RLS fixtureのPR→G6全工数へ訂正。正式教材章制作とB50最初の結果を混同しない。
- Auth確認はHTTPS後の既知アプリlogin/原110再承認、reset buildは別依存。全教材採用はWindows/iPhone等の210成立まで保留。画像は安定bucket/path正本・所有値検証、通知read_at一方向server時刻、全runメール台帳、全suite物理操作/QR/隔離事前probeとINVALID、中断再開・SQL復帰を設計。実行可能性や値を創作しない。
- 独立Codex native criticが原D4/原10と最新修正を実読しD4限定必須0。任意のwall/active/excluded-wait計時分離を記録。全84や最新外部相互合意の代替ではない。
- evidence/20261004-design-adoption: 原11/18部分差分を一時適用し32章/全FR/84依存/元状態と空節目保持を確認。現行84全セル/最終入力/14receipt SHA/所有PID・PG不存在/一時HOME除去/公式保存部分rawとheaders SHAを確認。全原同期や正式ゲートは未達。アプリ/新検証code・build・端末/cloud/公開へ進めない。goal active、freeze/implementation_ready=false。

## 2026-10-04 JST / 2026-10-03 16:44 UTC: 残51比較案と全84章依存の対応

- 設計のみ。残51判断を17×3比較案へ具体化し、先行33と合わせ原31章の84依存（83 B＋C8）を6案へ接続。84は全台帳/全goalではなく、C7ほか承認・Auth/D4G6/QA/P1G1を保持。全件未採用、原同期未適用。
- 実Droid11試行10成功1timeout。最初のOpus high空rawを意見なしとし以降medium。Opus必須4→1→1→1→0を修正、Gemini早期0を合意にしない。v5双方、残51指定範囲の必須0。相互の実意見への反論/読了範囲/任意2を保持し、原全文/先行33全文/実測/正式G6/100点/実装許可へ外挿しない。
- B50方針用本番書式fixtureと各正式章G6を分離し、重章本文を本番1章目前へ先行要求しない。B1原依存/A9/15記入、B85導入章と遅延commit、B114保存URLとUTC/JST、B67/100期限、B110/105、B14全変数、B63UTF8/CRLF、B115select/update等を補正。
- evidence/20261004-design-remaining-decisions: 原10baseline SHA不変/原51・84行一致/v5 input一致/11 receipt SHA/所有PID・PG不存在/一時HOME除去/公式6rawと7headers記録SHA/入力MANIFEST同一確認。UTF8/空白/行末を確認。既存code変更保持、アプリ/新検証コード・build・実機/クラウド/公開は進めない。goal active、採用/原同期/正式承認/全体完成未了、freeze/implementation_ready=false。

## 2026-10-04 JST / 2026-10-03 15:54 UTC: 33判断の具体比較と現行P1/G1照合

- 設計のみ。原84判断のうち旧3体験案に正確な番号言及のなかった33件を、開始資源/性能、投稿/Auth/画像/Realtime、G6/拒否試験の3比較案へ接続。各候補/代案/失敗/必要証拠/依存/影響/主体/期限を具体化。残51は個別比較の充分性未監査。全84採用/原同期/実装開始ではない。
- B70親＋位置NOT NULL/範囲/一意性、B71全書込終了形と画像/空/公開、B107 grant/policy別変異と42501誤因、両物理OS/host範囲/版固定/2時計、正式read4×2/D4軽重各3を整理。B118/119のPhase2期限とP1/G1条件を分離。
- 実Droid8試行。v1正確な入力path不備2件は無効（Opus未読保留、Gemini空raw/所有process停止）。v2 Opus必須2、v3必須1を修正。原16の5列/8列差による13行誤転記を直し22期限セル照合。v4双方限定必須0、実v3意見への一致/反論を記録。v4 Gemini low/Opus5.5 medium、他medium。原全文/実機/学習者/正式G6/100点へ外挿しない。非必須2は未決保持。
- evidence/20261004-design-decision-comparison。原7hash一致/最終review input一致/公式raw4+headers4 SHA一致/owned PID8不存在確認と一時HOME除去。原14のFR番号誤記は既に訂正済み、01再承認は未証明。PDF既決と14旧配布文言は要同期。コード/build/実機/クラウド/公開は進めない。goal active、原承認/全84採用/Auth/正式D4G6/QA/P1G1未完、freeze/implementation_ready=false。

## 2026-10-04 JST / 2026-10-03 15:30 UTC: 全31章の体験草案と84判断の原索引

- 最新指示どおり設計のみ。残る17章の操作/結果/概念/開始資源/復帰を草案v3にし、先行14章と原31章へ接続。全FRと84判断IDを保持。機能/新検証コード・build・実機/クラウド試験は進めない。
- 型診断とruntime例外を分離、80のSNS用開始snapshotを練習projectと区別。210の試験A/D/Bと旧password対照、290のW/追加メール需要と回復、310の全FR別受入/証拠再利用と不足時戻りを具体化。検索の古い応答/空入力、タグbackfillと通常RLS、bookmark解除と論理/物理削除を分離。
- 実Droid Gemini3.8Flash/Opus5.5 mediumは7試行6成功1timeout。v1 Opus必須3、v2必須1をGPTが修正。v3両限定必須0、互いのv2実意見を読んで一致/反論。原資料全照合・実走・理解・正式G6・100点へ外挿しない。Opus非必須2は未決保持。
- native証拠evidence/20261004-design-remaining-chapters。原7資料hash一致、最終review input一致、公式TypeScript/Expo/Babelのraw6件SHA一致。全84原行へ接続、草案に正確なID言及なし33件。言及と採用完成は別。全判断の具体案/理由/影響/証拠、資源/原承認、Auth/正式D4/G6/QA/P1/G1は未完。goal active、freeze/implementation_readyはfalse。

## 2026-10-03 14:55 UTC: 画像〜交流/通知の体験カードと原依存の設計比較

- 設計のみ継続。前回v7の追加4提案を登録→初投稿v8へ反映。130/150/160/170/180/190/200/260の開始資源・最初の結果・概念・回復を新草案v3で具体化。原31章/84判断ID・全FR、既存Auth/D4/G6/QA/P1/G1のgoalを保持し、アプリ機能/新検証コード・build・端末/クラウド試験は進めない。
- 130の一括/個別Saveと公開/保持、150相手への部分投稿公開3案、タグ240と既存B61、160相手への入口、170以後同時2画面、削除と4通知・200の新規契機を比較。media先行INSERT案をFK/親所有者RLSで補正。原posts購読はINSERT-onlyで削除UPDATE未配信、追加UPDATEは別契約と明記。
- 実Droid Gemini3.8Flash/Opus5.5 mediumで3rounds/6CLI成功。v1 Opus必須4を修正、v2追加補正4をv3へ反映。最終両限定必須0。Read範囲自己申告とv1原未読を保持、全FR/全資料/実走/正式G6/100点に外挿しない。v3非必須1（B61とDB一括確定の前提）を保持。
- 公式5資料を実HTTP取得してURL/UTC/raw/headers/SHA保存。現行DELETEフィルタ記述と原06の差を凍結前確認カードへ。SQL DELETE RLSとRealtime配信認可を区別。旧rendered観測はraw未保存の弱い根拠と明記。実project挙動は未測定。
- native証拠evidence/20261003-design-image-social。原7資料hash一致・原同期未適用、最新本文とreview input一致、owned PG停止/一時HOME除去。体験カード未具体化17章・全判断/資源/受入の採用、Auth/正式D4/G6/QA/P1/G1は未完。goal active、設計freeze/実装readyはfalse。

## 2026-10-03 14:24 UTC: 実装前の登録→初投稿体験を具体化、設計限定相互レビュー

- 最新ユーザー指示を優先し設計のみ。DESIGN.mdの索引/保存の根拠、親体験案、登録→初投稿のv7を整えた。既存候補を保持し、アプリ機能/検証用新コード・build・端末/クラウド試験は進めない。
- 完成SNSの利用者と途中章の学習者を分離。100登録/待機、110の状態別入口とメール/認証回復、120の同画面保存値確認とDB対照、130本人profile、140投稿詳細と限定結果確認、追加候補145本人一覧、170フォロー中timelineを接続。再起動を越える入力保持は未採用。
- 実Droid Gemini3.8Flash/Opus5.5 mediumで7版を相互レビュー。15試行中14成功、Opus v5初回timeoutを保持。最終v7は両限定必須0。Geminiの早期ACCEPTを相互合意とせず、Opus必須5→4→2→1→2(retry)→1→0を修正。追加提案4点は凍結前の課題として保持。全体100点/正式G6/学習者実走に外挿しない。
- 全原31章/84判断IDの範囲を保持。32章(145追加)/33章(110も分割)等は比較案、章数未凍結。原11/18/04/06の部分同期patchは未適用、4資料hash一致。最終v7の全変更を含むpatchではなく、Auth/権限の採用判断後に再生成する。
- native証拠evidence/20261003-design-onboarding: 入力snapshot/raw/receipt/SHA、owned process group停止と一時HOME除去。設計freeze/実装ready/P1/G1はfalse、goal active。次は追加提案とAuth/権限、画像公開/保持、交流・通知を全体の開始/結果/復帰へ接続する。

## 2026-10-03 13:21 UTC: ユーザー指示で設計・体験を先に固める段階へ

- 「設計と何をやるか、どういう体験をしてもらうかまで固めてから実装」という最新指示を優先。アプリ機能/検証用新コードを進めず、既存候補を保持。goalはactiveで設計の整合と体験具体化を行う。
- DESIGN.mdを原仕様優先の索引として新規作成。00/01/11のインターン＋独学者、A0端末編集→SNS→カメラ→同じコードWeb→説明力を章の操作/結果/理解/復旧へ具体化。31章の設計宣言を棚卸し、原未決依存と追加設計を記録。正式凍結ではない。
- 原APIのavatars1bucketと候補matrixの別bucket記載の不一致を確認。現在remote PR22 HEAD956e29bの64caseは原名へ修正済みで、30候補/34NOT_READY/採用0をread-only確認。新機能実装ではない。
- 画像案V1実Gemini NEEDS_FIX4/Opus5.5 NEEDS_FIX5。3軸/8組合せ、旧URL公開、NULL/CAS、アプリ表示とhash検証の分離へ修正。V2の完全なprocess/receiptは現環境に無く、空artifactを合格と扱わない。修正版と新体験案は三者再レビュー未完。
- 旧一時worktree/processは現環境に不存在、元git objectの一部はempty。既存sourceと証拠を保存し、remoteはAPIで確認。復旧のために実装再開やcopy/buildを行わない。記録evidence/20261003-design-alignment、設計案decisions/20261003-教材体験と実装開始条件の設計案.md。

## 2026-10-03 12:36 UTC: 全FR横断RLS草稿・プロフィールsliceとStorage実境界

- 新規d4-heavy本文/解答/画面図/開始契約と64case、30候補/34NOT_READY/正式採用0。旧投稿pilotは昇格せず、全SNS前章STARTと操作変数は未接続。
- 新規d4-predecessorプロフィール設定/表示/編集とtyped routes。入力破棄と再読込・結果不明・未作成時の案内を修正。unit10＋Auth20、TypeScript6.0.3を検証。同HEAD d46aa59のgates37123108659/SecretScan37123108734 success。
- SDKプロフィールV2は6意味チェック、7応答、拒否ごと直後の独立DB全2行×8列不変。公開matrixはV1 hash、native最終V2を区別。StorageV4は40意味チェック、private/public差・他者remove空配列・bytes/DB不変。14surface/catalog/Auth/Mailpit復元、第三bucket実操作は未測定。
- 実Gemini3.8Flash/Opus5.5 mediumが章とprofile各3rounds、計12CLI。GPT反証/修正後、最終両限定必須0。SELECTFALSE誤説を仕様とTEMP実測で撤回。100点/正式G6/新profile実機へ外挿しない。
- 証拠evidence/20261003-d4-production-slice、判断decisions/20261003-D4横断章とプロフィールStorage境界の実測.md。clockは着手前開始/run OPEN/humanactive null、初期2delegate詳細時計の欠落を開示。private証拠/HTML/資格情報は公開しない。
- 全体goal active。プロフィール画像とStorage実装、投稿/画像/詳細、follow/timeline、reply/repost/like、通知生成/read、Realtime/owned graphを続ける。正式学習ログ/対照版/read4人2rounds/軽重各3exec・隔離、外部Auth、C7/C8、P1/G1と原承認は未完了。

## 2026-10-03 11:49 UTC: D4時計・教材ソース照合、新規実モデル2runと相互報告review

- public e8d7964に時計/originとtests、CI入口を追加。成功resume/集計の観測値も永続化、巻き戻り・boot変更・不正retry・重複終了を拒否。OPEN/null/formal falseを維持。ローカル112checks、同HEAD gates37120543540/SecretScan37120543510 success。CI D4 Python72の4bwrap skipは実隔離成功にしない。
- 修正private controller新規V2実Droid Gemini/Opus5.5 mediumが成功。新pilot223.146秒/125.471秒、model Popen/wait221.653秒/123.750秒。Gemini型失敗2回→自己修正、独立型/AST/origin/入力hash/出力snapshot/HOME除去を確認。18/12操作区間は終了、runはOPEN、正式D4/G6工数ではない。
- native誤読snapshot20を撤回、Opus V1 NEEDS_FIX8を修正、Gemini V1 timeoutは意見に数えない。rootのレビュー帰属誤記も原promptを保持して訂正。V2 code/V3相互report reviewは両exit0/限定必須0。全体100点へ外挿しない。V3 Opusはtextだけのレビューと明示。
- owned orphan childの実停止、malformed stdio7frameの全span記録を確認。別postrun11/5 observed対auditの一致・edit・snapshot・ledger bootを検査。env scan0だが同UIDread error5を残し、detach排除/全child不在を主張しない。空tool列future判定、二度目signal/SIGKILL、UTC逆行false-negative等は残る。
- 証拠evidence/20261003-d4-run-clock、判断decisions/20261003-D4開始時計と教材ソース照合.md。PR22はdraft、private証拠/HTML/資格情報を含めない。今回は教材/実機runtime不変、実機52を再実行していない。
- 全体goal active。次は着手前時計を持つ本番7役割RLS章と実ログ分配、plain/minus、正式G6 read/execへ進む。外部Auth、残G3、軽重各3回、C7/C8、P1/G1・原承認境界を保持。

## 2026-10-03 11:22 UTC: 最終本文の新ソースで故障実機52/52、相互レビュー限定必須0

- 最終Gemini App b12d4f/component41616bのV5は52種類52項目がtrue。未転送60.007秒/DB更新後応答保留60.009秒、結果不明観測16.640秒/16.570秒（WDA込）。native enabled属性/stale row、counterと独立DB、refresh後の表示、本人削除、peer存在とMetro reload送信・後続GET・trial A/B非表示を観測。応答再描画/peer個別認証/因果分離/要求UUIDは未証明、実メッセージ選択は未記録。
- V1〜V4失敗を保持。最後はprocess_not_live_wda→単独diagnosticでAppNotInstalledError。既存WDA16.12.8を一回144.4MiBのsource/DerivedDataへ復旧、profile/端末/certificate照合。build65二回と部分app後処理失敗を保存。1Passwordの明示codesign-fix情報でkeychain unlock、最終build0/署名検査/install0。bundle ID集合232→233、追加はWDAだけ。他appデータ/全設定不変は主張しない。元lock状態は未測定・再lockなし、WDAは次検証用に残す。
- 全5runのbefore/after計10snapshotでAuth63/profile20/posts18の全列hashが一致。raw receipt SHA対応表と時刻付き別SSHの専用5経路接続不可/record/session/marker不存在を保存。論理削除の物理行保持はrun中、cleanupで試験行を物理削除。model workspace/runtime21source不変、local Expo session消去、server失効は未測定。
- 実測報告V1はGemini限定必須0/Opus NEEDS_FIX9。未記録値を補完せず証拠と説明範囲を修正。V2相互敵対レビューで双方LIMITED_MEASUREMENT_REPORT_ACCEPT/必須0。Geminiの設定不変説とOpusのbaseline0説を双方が反証・撤回し、人工的な点数を撤回。最終controller全体の第三者検証ではない。根拠evidence/20261003-d4-chapter-revision、判断decisions/20261003-D4教材改訂と新ソース故障実機.md。
- public HEAD36ebff5、ローカル70zero skip/同HEADのCI成功は維持。ドラフトPR22本文を最終限定scopeへ整理、private証拠/HTML/資格情報はPRへ収録しない。全体goalはactive。次は正式G6のread/exec・clock、残G3、外部Auth、C7/C8、P1/G1を契約に沿って継続する。

## 2026-10-03 11:02 UTC: D4教材を改訂し最終本文でGemini/Opusが再制作

- ドラフトPR22の36ebff5。削除true/false/結果不明、試験投稿を使い切る条件、A→B→A、前章Appの一意な3行→5行接続を本文へ採用。15コード345行10711bytesは維持。最終本文SHA93145、開始snapshot9d6d。G3文体PASS、残る4観点は正式判定しない。
- 最終本文から実Droid Gemini/Opus5.5 mediumのV4が独立制作成功。App b12d4f、componentはGemini41616b/Opus bb545。Geminiの型失敗→修正を含め原イベントを保存。独立inventory/実bwrap型検査/AST接続確認、一時認証除去を確認。ToolSearchが残るため正式知識隔離ではない。
- ローカル70/70 zero skip、GitHub gates37117733108とSecret Scan37117733063は同HEAD SUCCESS。CI D4 58件の4skipはbwrap不在として明示、本文復元12件PASS。過渡失敗と中間本文のV3制作も保存。
- 故障preexec Gemini V2/Opus focused V3は限定必須0。Opus V2のprovider内容判定失敗は意見に数えない。GPTが事後runtime差分コピーとMetro false時待機、固定エラーstage/codeを追加。新ソース実機V1はMetro待機不備、V2/V3はWDA前で失敗し、V3のコードprocess_not_live。Auth63/profile20/posts18のfull-row SHAは毎回復元一致。USB1台、専用5port/所有record/session不在も別SSHで確認。固定service名診断とsession外側timeoutを修正中。
- 正本evidence/20261003-d4-chapter-revision。旧通常29/29・旧故障25/25を今回App b12へ転用しない。全体goalはactive。新source故障、正式A5/D4/G6、時計/隔離/軽重各3回、外部メール、C7/C8、P1/G1を継続する。

## 2026-10-03 10:18 UTC: Gemini生成D4ソースの実iPhone通常操作29/29

- 前段モデルが章から作ったApp/componentを凍結し、所有Auth台帳と制作側全run leaseを接続。第三試行の記録29件すべてPASS（28種類の名前、同名2件はMetro/SSH別停止）。A→B→A、他人false＋DB不変、本人true＋物理行保持、実reload＋新規GET＋復元を今回のモデルsourceで測定。
- 最初の2試行はWDA前のprocess所有照合で失敗（13/17、14/17）として保存。fork/execとPython再execのcommand変化を修復し、旧processを所有条件で限定回収。資格情報/actorはstdin/RAM、global resetなし。
- 第三試行はAuth63/profile20/posts18のfull-row SHA256が前後一致、所有fixture回収、専用5portとremote record/session不存在を別SSH読取で確認。Expo local sessionSecret消去は確認、server logoutは未測定。
- 証拠evidence/20261003-d4-model-device、判断decisions/20261003-D4モデルソース実機通常操作.md。コードHEAD eab8f7fは維持。前段の別App故障25件を今回sourceへ転用しない。
- 実測後Gemini/Opus V3は両LIMITED_ACCEPT・必須報告修正あり。原receiptを保持してrun/hash/重複名/legacy回収と計測限界の対応表を追加。sourceafterは後付け再観測、lambda記録は完全なtraceではない。章改訂提案をnativeに保存、同ID再送は現行UIで不可と明記。
- V4相互敵対レビューは双方LIMITED_ACCEPT_WITH_REMAINING_GOAL、報告修正必須0。9制約と教材未採用を保持。誤った停止対象名・原receipt書換・読まなかったとの断定・一覧消失からDB原因断定をGPT/Opusが反証。全文候補を別保存し、15コード345行10711bytesが元章と完全一致を独立確認。共有章/manifestへは未採用。
- 全文候補のV5は両モデルTEXT_CANDIDATE_ACCEPT/必須0。GPTが両者の見逃した置換行数6→5と説明2箇所を機械照合で追訂正しv2へ別保存。15コード不変、置換snippetは実モデルAppの部分文字列と一致。v2のモデル再レビュー・共有章反映・新本文から再制作を捏造しない。
- **全体goalはactive**。新source故障注入・教材品質・正式A5/D4/G6・時計/軽重各3回・外部メール・C7/C8・P1/G1は未完了。静的レビューと実機通常操作を分け、全体100点は主張しない。

## 2026-10-03 09:49 UTC: D4章からモデルが選ぶworkspace制作に進行

- 非形式の限定MCPとしてread_file/edit_file/typecheckだけを追加。公開章・Auth前章19ソースを凍結、App/componentの2出力をCASと制作側保持hashで照合。資格情報・provider・UI・任意shellは公開しない。
- 実DroidのGemini3.8 Flash/Opus5.5をmediumで独立起動。V1は両CLI終了0でもmetadata互換エラーで制作失敗として保存。V2は両モデルが章と開始状態を読み編集し、制作側の別inventory・実bwrap型検査・AST接続で成功。Geminiの型検査失敗と自己修正も保存。
- 最終ローカルD4 58/58と本文復元10/10 PASS。実型検査9隔離probe、外部差替え/無断出力/不正JSON/巨大frame/audit停止/notification無応答を確認。最終MCP互換差分の実subprocessは別測定であり、V2出力を最終MCP再実走へ拡張しない。
- 最新ドラフトeab8f7f。同HEADの[gates](https://github.com/kouiso/sns-app/actions/runs/37114564903)と[Secret Scan](https://github.com/kouiso/sns-app/actions/runs/37114564873)がSUCCESS。既存Auth SDK57依存を再利用し、CI D4は58対象のうちbwrap不在の4明示skip、本文復元10件はPASS。ローカル58件zero skipとCI成功を分け、欠落正式入力も未判定を維持。
- 証拠evidence/20261003-d4-model-workspace、判断decisions/20261003-D4モデルworkspace制作.md。実Gemini/Opusの相互敵対レビューV3は双方LIMITED_ACCEPT/必須0、native最終MCPも限定必須0。型抑制scanと58件zero skipログをhashへ束縛。全体100点へ拡張しない。
- **全体goalはactive**。Droid ToolSearchが残るため正式知識隔離を主張しない。モデル出力の実機実走・reloadと制作側全run lease接続、教材品質、正式D4/G6、外部メール、C7/C8、P1/G1は未完了。旧実機hashの証拠を今回生成Appへ転用しない。

## 2026-10-03 09:28 UTC: D4公開入力・章頭・controller leaseの限定部品を検証

- ドラフトPR [#22](https://github.com/kouiso/sns-app/pull/22)、ed3a29d。Auth前章19ソースだけの開始候補と投稿画面を組み立てる本文を追加。正式START/原承認/merge/公開を変更しない。
- 公開入力17、lease10、本文復元10、AST構造9の46検査PASS。本文とApp2変更だけで20ソースを復元し、実tscとAST/G3成功。復元はテキスト整合証拠で独立学習ではない。
- 無接続JSX・虚偽合格本文・formal flag・制御文字・空query/fragment・UUID不整合を敵対実測して修復。取得途中と解放途中のthread forkを親異常終了/子存命条件で再現し、mutex/FD登録保持により再取得を検証。期限超過とrenew metadata失敗は成功扱いを拒否。
- Gemini3.8 Flash/Opus5.5はmediumの実CLIで相互批判。GPTが再現・修正。V4は双方LIMITED_COMPONENT_ACCEPT/必須0。[最終gates](https://github.com/kouiso/sns-app/actions/runs/37112965924)と[Secret Scan](https://github.com/kouiso/sns-app/actions/runs/37112965907)は同HEAD SUCCESS。正式欠落入力は未判定を維持。
- evidence/20261003-d4-input-start と decisions/20261003-D4公開入力と章頭候補.mdへ原文・反証・hash・CIを保存。旧iPhone25/25を新開始状態の実機証拠へ転用しない。
- **全体goalはactive**。モデルCLI外側の専用MCPでworkspace Read/Edit/typecheckを閉じ、制作側driverだけへ公開入力・資格情報・実機操作・全run leaseを接続する。15分割/周辺文脈/プロフィール見出しの教材課題も保持。章のみread/exec、新開始状態のiPhone実測、正式D4/G6、外部メール、C7/C8、P1/G1は未完了。

## 履歴 2026-10-03 08:57 UTC: D4の9テーブル・章候補・故障実機を追加した最新ドラフト

- ドラフトPR [#22](https://github.com/kouiso/sns-app/pull/22)、881167c。D4の公開35ソースをmanifestへ固定し、39ファイル追加変更と実測値修正4ファイルを保存。正式本文/START/承認/merge/公開は変更しない。
- 3 migrationを実適用、実SDK69/69 PASS。旧trial M1の28項目とは別契約。不要definerと通知filterless UPDATEの穴を追加移行で修復。catalog before/after一致、並行削除/子追加の残存条件は未解決として保持。
- 実iPhone最終25/25 PASS、App/RlsTrialの前後hash一致。A/B権限・論理削除・物理行・実reloadと新規API取得・復元、未転送とDB更新済み応答保留を別測定。60秒保留より前の21.240秒/20.815秒(WDA込)で結果不明と操作回復を確認。旧20秒保留は最終timeout証拠に不採用。
- 所有記録の永続化: 15units、実DB seed/reset12、明示移行8、read-only照合5がPASS。旧bytes保持、3fields、0700/0600、他人行/Auth/profile保護。3file一括atomicやWSL再起動/初回powerloss/全run leaseは主張しない。
- Gemini3.8 Flash/Opus5.5はmedium。相互敵対レビューで過剰主張と実測値不一致を訂正し、V7双方LIMITED_CANDIDATE_ACCEPT/必須0。GPTが実測・hashを照合。最終同HEADの[CI gates](https://github.com/kouiso/sns-app/actions/runs/37111264243)と[Secret Scan](https://github.com/kouiso/sns-app/actions/runs/37111264242)がSUCCESS、19明示skip/欠落正式入力はUNJUDGEDのまま。
- 今回の5process・fault markers・isolated CLI login・所有投稿を片付け、専用Supabaseと共有アカウントを保持。証拠evidence/20261003-d4-preconditions、詳細decisions/20261003-D4-RLS章と実機限定検証.md。
- **全体goalはactiveで継続中**。次はD4専用profile/input境界と制作側driver/UI全run leaseを実装し、章頭からの独立実走・readへ進める。正式D4/G6、外部メール、C7/C8、SNS全体、P1/G1を100点・完了へ読み替えない。

## 履歴 2026-10-03 07:57 UTC: Auth実アプリ・実iPhone復帰を追加した最新ドラフト

- ドラフトPR [#22](https://github.com/kouiso/sns-app/pull/22)、946a885、84コードファイル。Auth候補19ファイルを追加し元SDK57開始状態を保持。原承認/merge/教材公開は変更しない。
- 実Supabase JS/AsyncStorage/URL helperとAuth UI、保存/更新、cold/warm受信を実装。Node20 PASS、実receiver＋SDK13項目PASS、実iPhone通常9操作＋503故障4項目PASS。最終App前後hash一致。Mailpit hashを手動exp URLに組み立て、外部メール内クリック/custom buildの証明にしない。
- Gemini3.8 Flash/Opus5.5はmedium。相手の見解と実ソース全文を読み、双方LIMITED_CONTROLLED_CANDIDATE_ACCEPT。GPTが成立した競合を修復・実測し、永久喪失/自動URL消費/永久loading主張を反証。timeout/modal/入力追記/故障注入不成立も履歴保存。
- 同一HEADの[CI gates](https://github.com/kouiso/sns-app/actions/runs/37107779563)と[Secret Scan](https://github.com/kouiso/sns-app/actions/runs/37107779605)がSUCCESS。新候補npm ci/20tests/typecheck成功。既存19明示UNJUDGED skipと正式教材/開始状態/G4/EPUB/PDFの欠落入力は未判定。
- 証拠evidence/20261003-auth-sdk57-app/status.json、詳細decisions/20261003-Auth-SDK57実アプリ候補.md。試験用loginと今回起動したMetro/reverse/proxy/WDA/iproxyを片付け、続くD4用ローカルSupabaseを保持。共有アカウント/他サービスは変更しない。
- **全体goalはactiveで継続中**。正式Auth/外部メール、D4の開始状態・工数/独立read/exec、正式G6、C7/C8、P1/G1は未完了。次はD4の具体的な開始状態と章を進める。未回答/未測定を100点・完了へ読み替えない。

## 履歴 2026-10-03 07:25 UTC: トリオのAuth受け口試作・実測を追加した最新ドラフト

- ドラフトPR [#22](https://github.com/kouiso/sns-app/pull/22)、`a5f3436`、65コードファイル。コードの作業場所は `/tmp/sns-trio-ci-review`。原承認、merge、教材公開は変更しない。
- 最新ローカルcomponentはG6 56件＋SDK57整合/失敗経路18件＋Auth受け口18件＝**92 PASS / skip 0**。Authの実GoTrue REST adapterは別の**8項目 PASS**。SDKを呼んだことやApp復帰・外部メール到達の証明にはしない。8項目の再実行を種類数へ足さない。
- `type=recovery` の改変を目的の証明にしない。ログアウト後に成功キャッシュから再認可しない。指標は状態変更数ではなく `set_session_calls`、3つのcallbackの個々のtokenを出力前に検査する。既知のrollback・SDK/native・本番purpose証明の未解決は保持する。
- Gemini 3.8 Flash / Opus5.5はいずれもmedium。相互の見解と修正後コードを読み、双方 `LIMITED_COMPONENT_ACCEPT`。コード実行とhash計算はGPTが担当し、モデルの静的レビューと区別する。初回CLI180秒timeoutも履歴として残し、承認へ数えない。
- **同じHEADの実CI gatesとSecret ScanがSUCCESS**。対象componentは73 PASS＋19明示UNJUDGED skip。欠落している正式教材/開始状態/G4/EPUB/PDFの合否は未判定のまま。SDK57固定MCPの両モデル13操作/4段階は引き続き限定統合証拠。
- 証拠 `evidence/20261003-auth-return/status.json`、`local-final.json`、`tests.log`、両モデルreview-v3、`ci-final-a5f3436.log`。最終5ファイルのhashは実測・レビュー入力・公開コードで一致。詳細は `decisions/20261003-Auth復帰受け口の限定試作.md`。
- **全体goalは継続中**。実Appのクライアント/セッション保存/受信フック/画面、実機と外部メールでの復帰、D4重い章の開始状態・工数/独立read/exec、正式G6、C7/C8、P1/G1は未完了。`ssh macmini-lan` は接続できる。必要資源の未回答をローカル成功で埋めず、実アプリ組込みと計測準備を続ける。

## 履歴 2026-10-03 07:01 UTC: SDK57候補と実走経路を追加したドラフト

- ドラフトPR [#22](https://github.com/kouiso/sns-app/pull/22)、`410b5c8`、60コードファイル。正本は `/tmp/sns-trio-ci-review`。merge/教材公開/原Phase0承認は変更しない。
- SDK57候補は2章、plain2本、導入会話だけを除く実験版1本、14ファイルの共通ソース。正式R2ではない。正式開始状態/SDK採用/G3/G6/初心者通し実走はfalseのまま。
- Geminiが文面を限定ACCEPTした後、Opusがターミナル中断で準備変数が消える問題を反証。GPTが採用し、diskmarker・依存再試行・visibleSTOP・差分確認後のcommitへ修復した。両者はV2のcontrolledLinux/macOS/Node22候補文面に限定ACCEPTで合意。レビュー後の段落区切りだけの変更は文字列を照合し、構造5ファイルを再検証した。
- ローカルG6 component56＋候補整合/シェル失敗経路18＝74 PASS/skip0。18件のnpm/Expoはstubであり実ランタイムではない。未ログインwhoamiは実SDK57 CLI＋隔離homeでexit1を別確認。Ruff/Mypy・構造5ファイル・文体2章・bash50ブロックもPASS。
- SDK54の既定11操作を保ち、SDK57は1回のApp全体編集と13操作/4フェーズ。14ファイル全体・通常index・初回コミット・clean状態から開始し、App-only差分・HEAD親/件名・他13ファイルの不変を照合する。
- Gemini3.8 FlashとOpus5.5が各1回sole-MCP経由で新版を実行。各章読取1回/13操作/全denial0/finalize1。rootがtrace/章の行束縛/全4phasehash/14ソース/最終Git状態を独立照合。認証コピー600/削除済み。固定抽象操作と非対応範囲のヒント付き接続試作であり、独立A5学習・空cwd・起動時syscall隔離・Metro/UIの証明ではない。
- `410b5c8`の実[Actions gates](https://github.com/kouiso/sns-app/actions/runs/37104822120)と[Secret Scan](https://github.com/kouiso/sns-app/actions/runs/37104822109)成功。対象component testsは55PASS＋19明示未判定skip（取得済みreceipt未指定/bwrap未導入）。正式G3/G4/開始状態/EPUB/PDFの未判定も維持する。
- 証拠正本: `evidence/20261003-sdk57-candidate-model/status-v2.json` と `root-verification.json`。以前の物理iPhone証拠は同じApp/lockだけで、新14ファイル全体や新章のQR/初心者通し実走には転用しない。
- **全体goalは継続中。Auth外部メール/App復帰、D4重い章の開始状態・工数/独立read/exec、C7/C8、P1/G1は未完了。** D4受入条件を `decisions/20261003-D4重い章の受入条件.md` に整理し、過去の時間を捏造して埋めない。次はAuthの実App復帰とRLS重い章の開始状態を準備する。

## 2026-10-03 8eaf95d時点のコード候補（履歴）

- ドラフトPR [#22](https://github.com/kouiso/sns-app/pull/22)、`8eaf95d`、35コードファイル。正本は `/tmp/sns-trio-ci-review`。原作業ツリーの設計・端末・認証資料は含めない。
- 統合後QA27スイート、G3自己テスト33、G6関連50、試作7対象の5検査・引用・SDK54型検査はPASS。実章の固定11操作でApp編集・Git保存・一時編集・復元を実bwrapで検証し、失敗後再開/弱いwrite判定/設定検査順/最終改変/証拠改変を拒否する。
- 最新8eaf95dの実Actions gates/Secret Scanは成功。CIのG6は34 PASS＋16明示未判定skip（取得済みreceipt1、bwrap probe1、live-reload14）。ローカルは50 PASS/skip0。正式教材・開始状態・G4・EPUB/PDFの入力欠落も未判定のまま。コードCIの緑を正式合格へ転用しない。
- 最新sourceに対しGemini/Opusが各11操作をsole-MCP経由で完走。rootは正規化traceと全5phasehashを照合。これは固定操作契約・操作数等のヒント付き接続component検証であり、本文だけの学習/空cwd/startup隔離/全denialログ/Metro/UIとの束縛は未証明。一時認証コピーは削除。
- SDK57固定候補は両OS bundle200・型検査PASS。今回の候補をiPhoneへ開き、初期2文＋編集後の緑の第3文を同じWDA sessionで観測した。新sessionによる旧観測の汚染はINVALIDとして保持し、手動復旧後のfresh editで自動反映を再確認。QR/初心者通し操作/正式開始状態の証明ではない。
- GPT/Gemini/Claudeの指摘を修復し、最新artifact/Git componentはtrustedcontroller startに限定APPROVE。外部任意Git repoのreplace refs/grafts等はscope外。正式G6execはNOT_READY、readはNON_FORMAL。Auth外部メール/App復帰、D4工数、C7/C8、P1/G1は未完了。
- 今回だけのMetro/SSH reverse/WDA/iproxy/LANproxyを停止、専用Expo CLIセッションはログアウトした。共有設定・端末アカウント・証拠は保持。Macは空き約2.8GiBのため追加ビルド/ダウンロードを行わない。
- 次は原制約（両OS・Expo Go・初心者へ有料Apple登録を要求しない）を守り、B11/B26のSDK57候補を教材手順/開始状態へ再適合し、章のみからの独立実走と実UI証拠を束縛する。原Phase0承認・C7/C8・正式凍結を変更しない。

## 2026-10-03 統合前の検証履歴: Gemini・GPT・Claude

前回のS0〜S3限定完了から作業を継続する。最新の結果と失敗は
`decisions/20261003-三者での継続検証.md`。下方の旧QA6 FAILは修復前の履歴。

- 既存QA: 全18自己テストスイートPASS。実配布成果物と実CIは未判定。
- 専用ローカルSupabase: Auth/投稿RLS/限定論理削除RPC候補の33項目PASS。
  外部到達・App復帰・D4全体・G6へ転用しない。実験で直接UPDATEの論理削除が403になる問題を発見した。
- G3/G6: 欠落検査と偽PASS経路を修復・独立再レビュー中。正式通過はまだ主張しない。
- 所有資源: 既存の停止中プロジェクトに変更なし。専用組織とテスト宛先の回答待ち。
- P1/G1: 未完了。原承認を保持し、C7/C8や正式凍結の未回答を捏造しない。

## 2026-09-19開始 / 2026-10-03更新: V3.5の限定単位S0〜S3はDONE

基準は `7f04545`、開始時の作業ツリーに差分なし。実行判断と完了条件は
`decisions/20260919-章表の下書き検査.md` に保存した。Phase 0の承認を取り消していない。
今回の `go` を製品SDKの再採用、01の再承認、C7/C8の回答やG1凍結へ転用しない。

### Mac mini 接続後の更新

ユーザー提供のSSH経路で両物理端末を確認。Android（Pixel 7 Pro / Android 17）は
Expo Go 57.0.9＋USB転送で初回表示・編集反映PASS。証拠は試作環境記録§8と
`evidence/20260919-a0-android/`。QR・Wi-Fi・初心者工数の証明ではない。
iPhone 12 miniはSSH経由の実機操作と画面取得が可能。2026-10-03に、
ユーザーが利用を認めた1Passwordの資格情報でApp Store認証を通過し、Expo Goを導入・起動した。
04:08 UTCのCOLD起動・表示・編集反映はPASS。証拠は試作環境記録§11と
`evidence/20261003-a0-ios/`。

### 完了した範囲

- S0: 04§10、05§4、06§7、08§12の固定入力109件を16のIDへ対応付けた。
  DB13の元項目を保持し、重複を統合。新たにB70〜B122を採番したが、判断済みとはしていない。
  対応証拠は `decisions/20260919-未決入力の対応.md`、未決の正本は16のまま。
- S2の下書き: 18をA0〜E全体・31章の**構成仮説**として作成。FR1〜15は一次実装章へ対応する。
  両OSの物理A0技術試作は限定PASS。初心者の章全体実走による章数・順序・境界の確定は未完了。
  フォロー関係のテーブルとRLSを、タイムラインから参照する前に置いた。
- 共通parserと正例・負例のテストを追加。実表は `draftStructureValid=true`、
  `declaredGateInputsComplete=false`。節目と直接証拠は空のまま。**G1未通過**。
  24テスト、変更2ファイルのruffとmypyを通過。mypyはimport先の既存ファイルを報告対象から
  分けた検証であり、既存 `markdown_scan.py:123` の型エラーを修正・合格したとはしていない。
- 既存QAを17本個別に再実行し **11 PASS / 6 FAIL**。6件ごとのB31処置案と保持すべき検出能力を
  `decisions/20260919-試作環境と既存QAの確認.md` に記録した。修正・G0全体の合格は未完了。
  統合後も新規1本を含む全18本を個別実行し **12 PASS / 6 FAIL**。
  失敗した6本の集合は開始時と同じで、新しい検査による追加失敗はなかった。
- 既存lockfileでA0試作2件の依存を復元し、型検査・Expo設定読取・Web静的出力を確認した。
  詳しい環境と初回のNodeエンジン警告は同証拠記録へ。物理端末・Expo Goの適合証拠ではない。
  共有既定値を変えず、適合Node 22.16.0でも再検証した。
- 親試作の既存依存と、契約指定のembedmd v1.0.0を一時配置して既存ゲートを実走した。
  文体の陽性自己テスト117件・陰性誤検知0、3章の文体・引用照合、統合gateはPASS。
  独立レビューも引用照合を再現した。ただしG3の残り4検査は未実装であり、
  G5も引用範囲の過不足を判定しない。G3全体・G6の通過証拠には数えない。
- 2026-09-19時点の独立コードレビューで当時の12ファイルの差分はAPPROVE。
  2026-10-03の追記と追加テストは、その過去のAPPROVEの対象に含めない。
  途中で見つかった期限判定、章履歴・例外範囲の偽PASS、型エラー、案内の同期漏れを修正し再検証した。
  当時の対象ハッシュを保存していないため、現在の差分への承認としては使わない。
  教材のG4受領証や局長の正式承認でもない。

- 継続検証: A0の2試作についてiOS/Android各用のMetro manifest・bundle取得が4件とも成功。
  このlocalhost検証単体では実機表示・編集反映は未確認。SDK案内と当時のApp Store表示の不一致、ADB経路別の観測を
  同証拠記録§7へ追記した。製品SDKの採用判断は変更していない。

### 未完了と再開条件

| 対象 | 状態・不足 | 担当 | 次の操作 |
|---|---|---|---|
| 物理Android A0 | PASS（USB転送での初期表示・編集反映限定）。QR/Wi-Fiは未検証 | 実機検証担当 | 両OSの技術証拠を保持。QRと初心者向け開始手順の独立実走は後続条件 |
| 物理iOS A0 | PASS（Wi-Fiでの初期表示・編集反映限定）。QRは未検証 | 実機検証担当 | Expo Go 57.0.9、両側同一Expoアカウント、ローカルネットワーク許可を開始手順へ反映 |
| 認証実測 | BLOCKED。専用プロジェクトの所有とテスト宛先を未確認 | 認証検証担当 | 所有・宛先・送信制限を明示して生成/外部到達/復帰/最終ログインを分けて測る |
| D4・G6 | BLOCKED。隔離DB、重い章、対照版、独立実走の証拠が未取得 | 試作担当＋独立検証者 | 専用試作で本人成功/他者拒否/DB状態を照合し、軽重各3体の到達・補完・失敗を残す |
| 章表の確定 | 未完了。初心者A0実走/D4/Authの実測、DB13等、C8の節目指定が残る | 設計担当＋局長 | 証拠と判断を章境界へ反映し、P1/G1の全条件と必要承認を別途判定 |

**S0〜S3の限定単位はDONE。両実機A0は独立検証済み。追加レビューの指摘・証拠は
`decisions/20261003-追加レビューと要求照合.md` に記録する。Auth/D4/G6、P1/G1は未完了。**
端末の場所と資格情報の利用権限は回答済み。導入・表示・編集確認をこちらで実行している。
本番本文・正式タグ・公開・配布・組版は開始していない。

### 文書00〜18の現在地

Phase 0の一括承認は `承認パッケージ.md` の2026-08-06記録が根拠。
以下はその履歴と、P1に向けて残る更新・承認を区別した現在地である。
下方の「Phase 0: 文書の状態」は提出当時の履歴として残す。

| 文書 | 現在地 |
|---|---|
| 00 企画概要 | Phase 0承認履歴を維持 |
| 01 要件定義書 | P1でFR13〜15を含む再承認待ち |
| 02 技術選定書 | Phase 0承認履歴を維持。候補試作版と教材採用版の照合は未完了 |
| 03 基本設計書 | Phase 0承認履歴を維持。後続の未決反映は別判断 |
| 04 詳細設計書 | ドラフト・P1承認待ち |
| 05 DB設計書 | ドラフト・DB13未解消、P1承認待ち |
| 06 API設計書 | ドラフト・P1承認待ち |
| 07 開発スケジュール | Phase 0承認履歴を維持。工数の実測更新は未完了 |
| 08 テスト計画書 | ドラフト・P1承認待ち |
| 09 教材シリーズロードマップ | Phase 0承認履歴を維持。後続教材は今決めない |
| 10 教材制作フロー | 既存ゲートを維持し、下書きparserの責務を追記 |
| 11 ターゲット・ペルソナ・UX定義 | Phase 0承認履歴を維持 |
| 12 文体・AI臭さ排除方針 | 既存本文と08-08改訂案を保持。G2の最終判定は今回未実施 |
| 13 記録・進捗管理規約 | 対象文書を00〜18へ拡張 |
| 14 マスターロードマップ | 工程・期限の正本を維持。P1未完了 |
| 15 カリキュラム骨子案 | ドラフト・章数の目安は実測前なので未確定 |
| 16 決定バックログ | 固定入力の対応と担当・期限・完了条件を補完。製品判断は未解決 |
| 17 文体正本の実測 | 参考資料を保持。承認不要という既存位置づけを維持 |
| 18 章分割表 | 新設したDRAFT / NON-G1。構造は検査済み、凍結しない |

## 2026-08-09: 章は Markdown で書く（局長決定）と、Phase 1 の3文書の書き下ろし

### 局長決定 — 前作 task-app と同じ順序で作る

局長の「task-app みたいなかんじじゃだめなん？」に対し、**その通りでよい**と答えた。
記録は `material/decisions/D24_執筆媒体と組版の順序.md`。

- 章の原稿は **Markdown で書く**。task-app は day01〜30 と appendix までこの順序で完成しており、
  やり方そのものに未証明の部分は無い
- **Vivliostyle はパートA の章が書き上がってから通す。**それまで組版の道具には触らない
- **B52・B53・B55〜B59 の7件は「組版に着手する時点で開ける箱」へ移した**（項目は消していない。
  A3 に従って期限を付け替えただけ）。**B54 と C7 は箱に入れない** — B54 は Markdown 原稿そのものの
  検査であって組版の話ではなく、C7 は章本文に書くリンクの宛先なので組版より前に要る

**手戻り表に #19 を追加した。**「原稿が1本も無い段階で、最終工程の道具を詰め切った」。
2026-08-06 の Vivliostyle 実測（D23）そのものは正しいが、教材本文が0本の段階でやる作業ではなかった。
#17 および 2026-07-28 の「捨てる予定の道具を磨き続けた」と根が同じで、
**成果の形（N件起票した）が取れる作業が、目的から離れていることを覆い隠す**型である。

### 書く前のゲートが、初めて実際に効く状態になった

D1-1 と D15 が「同じPRで置く」と定めていた道しるべ2本を、**この日まで置いていなかった**
（別ファミリーのレビューで指摘された）。

- `curriculum/README.md` — これが無い間、`material-writing-gate.sh` は
  `[[ -d "$ROOT/curriculum" ]] || exit 0` で**常に不活性**だった。しかも外から見ると
  「ゲートが効いて通した」のか「ディレクトリが無いので何もせず通した」のかを区別できない。
  **搬入した機構が一度も効いていない状態**を、仕様として固定したまま放置していたことになる
- `material/reviews/g4/README.md` — 同じ理由（D15）

**README.md 自身はゲートの対象外にした。**教材本文ではなく道しるべであり、
対象にすると README を直すのに文体スキルの読み込みが要る。

### 書く前のゲートに、別ファミリーのレビューが5周連続で抜け道を出した

`curriculum/README.md` を置いてゲートが実際に効き始めた（上）あと、
別ファミリーのレビューが**同じフックから5周連続で抜け道を出した**
（レビュー全体では5周で31件。うち書き込みゲート本体が8件）。

| 周 | 抜け道 |
|---|---|
| 1 | `git checkout -- <章>` / `find <章> -delete`（**実行ファイル名だけ**で読むだけと判定） |
| 2 | `cat <章> && rm <章>`（**1語目だけ**で判定） |
| 3 | `sort -o <章> <章>`（**引数**で書ける） |
| 4 | `git -c diff.external=... diff <章>`（**設定の差し込み**）／`rm -rf curriculum`（**ディレクトリ単位**） |
| 5 | `rm -f curriculu?/ch01.md`（**glob で字面が一致しない**）／`rg --pre <外部コマンド>`／**先に `git config` で永続化された外部コマンド** |

**毎回「今度こそ塞いだ」と書いて、毎回別の面が空いていた。**
根は1つで、このフックが**「読むだけの側を列挙する」設計**であることにある。
列挙は必ず漏れる、と冒頭に自分で書いておきながら、反対側で列挙をやっていた。

**5周目で方針を変えた。塞ぐのをやめ、外す側へ倒した。**

- `sort` `uniq` `awk` `less` `more` `find` `rg` `git` を一覧から外した。
  **`git` は「先に `git config` で永続化された外部コマンドを `git diff` が起動する」経路が残り、
  コマンドを書き換えない限り塞げない**（このフックは書き換えをしない）
- 実行ファイル名によらない検査を2本足した（`-o` / `--output` の存在、環境変数の前置き）
- **展開前の字面ではなく、実際に展開してから対象を判定する**（`rm -f curriculu?/ch01.md` は
  文字列 "curriculum" を含まないが、シェルは展開する）

残った一覧は `grep` `cat` `head` `tail` `wc` `ls` `file` `stat` `diff` `cut` `nl` `column` と
ハッシュ値の計算だけである。**それ以外はスキルを読み込んでから行う。**

**検査スクリプト2本にも、緑を返す欠陥が見つかった**（`check_step_length.py` のフェンス走査、
`check_visualization.py` の表の数え方）。詳細と、D14 の分類方法そのものへの含意は
`decisions/D14_検査スクリプトの実走結果.md` の追記に書いた。

### Phase 1: 04・06・08 を書き下ろした

Phase 0 の承認（2026-08-06）で着手条件が満たされたので、スタブ（目次予定のみ）だった3本を書いた。
**いずれもドラフトであり、凍結していない。**

| 文書 | 前 | 後 | 中身 |
|---|---|---|---|
| 04 詳細設計書 | 46行 | 約1060行 | 全画面の部品・状態・検証・エラー表示、ネイティブ設定、Realtime 購読、**機能・ファイル・環境の依存グラフ**（G1 の入力）、Supabase クライアント初期化とセッション寿命管理 |
| 06 API設計書 | 35行 | 約1030行 | **9テーブル全ポリシーを `CREATE POLICY` まで書き下ろし**、select/insert/update/delete を分け、`using` と `with check` の違いと「これが無いと何が漏れるか」を1行ずつ。トリガー2種・Realtime 購読契約・Storage のパスとポリシー・エラー6分類 |
| 08 テスト計画書 | 47行 | 約1130行 | テストを6層に切り、**認可（RLS）を結合から独立させた**。06 の全ポリシーを1本ずつ、学習者が再現できる手順で検証する表。実機手動確認15項目、メール上限に当たらない手順 |

**§11（組版成果物の検査観点）は拡張していない。**D24 に基づき「組版着手時に見直す」の1行だけ添えた。

### 敵対レビューと総点検で見つかったこと

各文書を2つのレンズ（文書間の整合／書いたとおりに作れるか）で反証し、成立した指摘を処置した。
そのうえで3文書を通した総点検を行い、**文書間のねじれを10件**見つけて直した。主なもの:

| ねじれ | 処置 |
|---|---|
| **04 §10 が「05 §4 課題2〜6 の期限は P1。06 と 08 の両方がそう扱っているため」と書いていたが、06 §7.1 は P1 に置いていない**（1件ずつ別の期限を置き、しかも「04 の期限は過ぎた。置き直した」と自ら宣言していた） | 04 と 08 の行を 06 に合わせて3行に割った。**同じ未決に2つの期限が立つのは A3 が禁じた型** |
| 「投稿の途中失敗」を 04 は「06 は引き取っていない」と書き、06 U13 は「引き取った」と書いていた | 06 U13（B1）に寄せ、04・08 の指し先を直した |
| 04 の Realtime 購読表が 06 §4.2 と行数が違った（`likes` の delete を分けていない） | 行を分け、**DELETE にはフィルタも RLS も効かないのでアプリ側の判定が要る**ことを 04 側に書いた |
| 08 の H2 が「`app.json` に書いた日本語がダイアログに出る」と断定していたが、04 §2.1 は「**ストア版の Expo Go では出ない**」と結論していた | B5 の両分岐で成立する書き方に直した。H5 に落ちていた B5 従属も足した |
| **削除済み投稿の子テーブル（いいね・タグ・画像）の検証が 08 に1行も無かった** | 06 が4か所で警告していた穴。08 §5.6 に検証行を足し、**16 B27 の論点そのものを子テーブルまで広げた** |
| 07 が 06 を「エンドポイント仕様」と呼び続けていた（2026-07-26 に消滅した前提） | 07 §1 の完了条件と「現在地」を差し替えた |
| **14 の Phase 1 完了条件が「01 への FR13（ネイティブ機能）追記」と書いていたが、01 でネイティブ機能は FR15、FR13 はメール確認** | 14 を訂正し、再承認が出ていない事実を B69 として起票 |

### 台帳へ起票した未決

**B60〜B69 の10件と C8。**いずれも「どの文書にも未決として立っていなかったもの」で、
複数の言い方で調べたうえで不在を確認している（13 §2.1 の調査規約）。

- **C8 は起票漏れの是正**。D1-6 が章分割表の `節目` 列を「D6（局長判断）で埋める。局長判断キューへ」と
  決めていたのに、**16 の全文に「節目」が0件**だった。10 §4 は「節目の章のみ局長審査」という
  ゲート分岐を持つので、列を空欄のまま凍結すると翌日に表を開け直すことになる
- **B10 の期限を P1 から B1 へ置き直した**。項目本文が元から「章順に食い込むため B1 と同時決定」と
  書いており、P1 のままだと自分の但し書きと食い違っていた

### 文書番号の衝突を解消した

2026-08-08 の文体正本の作業が `material/17_文体正本の実測.md` を main に入れ、
**D1-6 が予約していた `17_章分割表.md` と17番が二重予約**になっていた。
**まだ実在しない側（章分割表）を 18 へずらした**（ファイルの改名は発生せず、参照13ファイルの書き換えのみ）。

### Phase 1 の完了条件に対する現在地

14 の Phase 1 完了条件5項目のうち、**満たしているのは「配布形式の決定」1つだけ**である。

- **05 §4 の未解決13点は 0/13。**1件も解消していない。すべて 04 §10・06 §7・08 §12 のいずれかが
  未決として抱えている。しかも **9（既定値を誰が入れるか）と 12（削除済み投稿）は、
  06 が論点そのものの拡張を要求している**ので、13点は「解消待ち」ではなく「論点が増えた状態」にある
- **各文書の局長承認は1件も出ていない。**04・06・08 の未決一覧はどれも最上位の期限が
  「05 の局長承認前」で、承認が動かないと上から順に閉じない構造になっている
- **章分割表（`material/18_章分割表.md`）が存在しない。**D1-6 が正本と定め9か所が参照しているが実体が無い。
  読み取りを集約する `scripts/curriculum-qa/chapter_table.py` も無い。
  **この2つが無い限り G1 の合否そのものが定義されない**
- G1 を始める前に決着していなければならない未決が **17件**ある（04 §10・06 §7・08 §12 が
  「章分割表の凍結前」を期限に置いた項目の合計）。うち B番号を持つのは B14・B47 の2件だけだった

## 2026-08-06: Vivliostyle 採用（局長決定）と、その影響の実測

局長が **Vivliostyle を教材の組版に使う**と決めた。**この決定は覆していない。**
「採用したとき何が変わるか・何が壊れるか」だけを実測し、
`material/decisions/D23_Vivliostyle採用の影響.md` に記録した。

**組版そのものは成立する。** `@vivliostyle/cli` 11.1.0 で捨て試作の章から PDF と EPUB が出た。
日本語は化けず（鉤括弧・約物・全角括弧すべて正常。テキスト選択も検索も効く）、
話者ラベル「磯貝）」形式は CSS のぶら下がりインデントで台本として組める。
ページ下部脚注・柱・ノンブルも CSS 組版で動いた。50章規模で PDF 34.8s / EPUB 6.9s なので
CI に載る速度である。**12 §1.1 の文体スペックの凍結内容は覆らなかった。**

**壊れたのは3か所。いずれも全ゲートが緑のまま壊れる。**

| 壊れ方 | 中身 |
|---|---|
| G5 × VFM | `embedmd` は終端正規表現に `\)` を要求するが、VFM は指示の括弧内に `)` があると（エスケープしても）指示行を本文として印字し、直後のコードブロックを段落へ吸収する。`});` で閉じる形は Expo / React Native で支配的。`chapter-expo-first-screen.md:82` が現に該当 |
| G3 の穴 | frontmatter・画像 alt・コードフェンスのファイル名・ブロック生 HTML は textlint が一切見ないのに紙面へ出る。加えて**ルビ記法が prh の禁止表現パターンを分断して無効化する** |
| exit code | `vivliostyle build` は組版の破綻を検知しない。コード行の切り落とし・画像404・指示行の本文流出・未展開 md でコードが丸ごと消える、すべて **exit 0** |

**G5 の設計は変えていない。** 壊れるのは組版段階であって引用方式ではないので、
10 §4 に組版工程を1段足し、「保証しないこと」に1項目追記し、執筆規約と検査を起票した。
**引用指示を `/^}\);/` → `/^});/` に直す案は採らない** — embedmd 側が exit 2 で落ちる（再実測）。

**B9（配布形式）が決着した。** 教材本文＝**PDF が正本**、EPUB を機械検査用に併産、
webpub は不採用（ZIP と Web サイトは C6 で既に不採用）。
配布は「2系統」ではなく**3系統**（教材本文／完成コード＝公開リポジトリ／章末スナップショット）
であることも、C3 と棚卸し文書との食い違いを直す形で訂正した。

**新規に起票した未決定は B52〜B59 の8件と、C7（局長判断）1件。**
C7 は章末スナップショットの置き場で、決まらないと PDF 本文からのリンクが書けない
（実測で、相対リンクは PDF 内に `localhost` として焼き付き読者の手元で死ぬ）。

**未実測として残したものが18項目ある**（D23 §6）。特に重いのは
判型・級数を1つも決めていないこと、**GitHub Actions 上で1度も走らせていないこと**
（速度の数字はすべて Chromium キャッシュ 382MB が温まったローカルの値）、
epubcheck 未実行、**日本語組版の細部を拡大検品していないこと**
（＝局長が Vivliostyle を選んだ理由の裏取りができていない）、
`scripts/curriculum-qa/` の26本が VFM 記法を通せるか未検証であること。

### この作業で反証によって取り下げた自分たちの断定

- 「CSS は `vivliostyle.config.js` の `theme:` にしか書けない」→ **誤り。`--style` も効く**
  （試していたのは `-s`＝`--size` と `--user-style` の2つだけだった）
- 「`{.class}` 属性は既定で無効」→ **誤り。見出しには効く**（効かないのは見出し以外）
- 「Chromium の追加取得は不要」→ **測定条件の誤り。** 先行実行でキャッシュが温まっていただけ
- 「`check_tag_balance.py` は引数仕様で落ちる」→ **誤り。** 未搬入の `scripts/build-zip.sh` を
  読みにいって `FileNotFoundError` で落ちる（教材本文ができても動かない）
- 「話者ラベル形式は組版で崩れない」→ **条件が抜けていた。** 話者行の間に空行が要る

## 2026-08-06: 制作前レディネス監査と、局長判断が不要な決定の確定

承認待ちの間に、**教材の制作を始める前に決め切るべき事項**を総当たりで洗い、
局長判断が不要なものを確定させた。記録は `material/decisions/制作前レディネス監査.md`。

監査は6次元を並列で棚卸しし、各次元の「未決定」主張を懐疑側が既定「不成立」で反証する形で行った
（13 §2.1 の調査規約を適用）。**65件が反証を生き延び、7件が棄却、80件は既決と確認された。**

**工程の骨格は実在し機能している。**G0〜G6・伴走ループ・証拠契約・改訂タグ・
トリアージ台帳の行仕様・13 の記録規約・07 の工程・14 の順序。欠けていたのは2つで、
決めたと書いてある物差しの実体が文体ゲートと G4 記録に集中して伴っていないこと、
決定どうしの順序が台帳に無く後に決めると前を壊す項目が同じ優先度に並んでいたこと。

| 確定したもの | 中身 |
|---|---|
| D1 置き場・命名・章ID | 下流16項目の前提。章分割表の正本パス、開発ログの置き場、`listings/` と B2 の関係を含む |
| D5 章の骨格 | 3文書に散っていた骨格を1つに。voice-spec の「床」を1項目ずつ仕分け |
| D8 文体の検出器 | **prh 辞書 16→57ルール。陽性 exit=1 / 陰性 exit=0 を実測**。12 §2.1 の6カテゴリのうち検出0件だったものを潰した |
| D14 検査28本の実走 | **◎（そのまま効く）は15本ではなく5本だった。**表外3本を追加し全28本を実走で分類 |
| D15 G4 の記録様式 | 受領証テンプレートを実ファイルで作成 |
| D16 ゲート例外 | 3ラウンド連続で迂回された記法を本文の外へ |
| D17 / D7 対照版とパート完了 | 対照版の品質下限、パート完了の判定時点 |
| D20 / D22 記録運用 | オーケストレーターの正体、RUN行の再定義、16件表への追記規則（#17・#18 を追加） |

**新規に起票した未決定は B35〜B51**（B37・B40・B43〜B45・B48 は欠番）。

**局長判断待ち**: D2 公開範囲の点検 ／ D6 節目の章の指定 ／ D12 blind-test の採否 ／
D18 G6 完走のための共有設定変更の許可 ／ B13 edu-creator（**判断材料の
`GENERICIZATION_PLAN.md` がリモート・全履歴を含めて0件**と確定したため、材料を作り直すか
材料無しで捨てると決めるかを先に選ぶ必要がある）。
**実機待ち**: D3／B26（10分）。

### この作業で見つかった自分の誤り

2026-08-05 に書いた「本作の命名では検査が exit=0 で緑を返す」は**測り方が誤っていた**。
`| tail -1` の後で `$?` を取り、検査スクリプトではなく `tail` の終了コードを読んでいた。
実際はディレクトリ渡しが exit=2（fail closed で正しい）、**1ファイル渡しが exit=0 かつ
`✅ OK（0 ファイル）`** で、欠陥は後者に実在する。訂正の経緯は監査文書の付記に残した。
D14 の全28本実走で、同型が7本で確認されている。

## 2026-08-05: 前作 task-app の資産を棚卸しして移植した

承認待ちの間に動かせる作業として、前作の道具を調べ直した。
記録は `material/decisions/task-app資産棚卸し.md`。

**判明したこと: 本作は前作の「手戻り16件」は引き継いだが、前作が実際に作った道具を
引き継いでいなかった。** 前作は検査スクリプトを28本＋テスト17本、教材執筆スキル一式
（272KB）、書く前に止める強制フック4本を持っている。本作が持っていたのは
`check_tone.py` 1本だけで、`.claude/` は存在しなかった。

これは 2026-07-28 に「捨てる予定の道具を磨き続けた」と記録した反復の、より正確な説明でもある。
**前作にテスト付きの検査群があるのに、それを見ずに作り直していた。**

| 移植したもの | 状態 |
|---|---|
| `material-writing` スキル一式 | `.claude/skills/` へ無変更で移植 |
| 強制フック4本（書く前に deny する機構） | `.claude/hooks/` へ移植。**対象を `curriculum/` へ変更**（本作の `material/` は設計文書なので、無変更だと設計文書が書けなくなる）。陽性/陰性6件で検知テスト済み |
| 検査スクリプト28本＋テスト17本 | `scripts/curriculum-qa/` へ搬入。**まだ1本も実行していない。**分類は B31 で確定させる |
| `@textlint-ja/preset-ai-writing` | ルート `.textlintrc.json` へ統合（依存追加は B2 と連動・未了） |

**新規に起票した未決定4件**: B31（G0 の道具一覧の書き直し）／B32（教材コードが lint を
通るかの検査）／B33（貼り先の整合の検査）／B34（12 に床/天井を入れる）。
あわせて、2026-07-31 のコミットが 16 に作っていた見出しの重複と表の区切り行の欠落を直した。

## いま何待ちか（2026-07-28 時点。上の 08-05 の作業は承認と独立）

**局長の Phase 0 文書レビュー待ち。** これが Phase 1 への唯一の関門で、
受注側でできることは下の「残っている作業」を除いて出し切っている。

- 承認してほしい文書と論点は `material/承認パッケージ.md` にまとめた（1画面で読める形）
- **01 要件定義書は FR13・FR14・FR15 を追記したため再承認が要る**
- C群のうち C1（販売チャネル・価格）と C2（想定期間）は「今は判断しない」で処理済み

### 残っている作業（承認と並行で進められる）

| 何 | 状態 |
|---|---|
| P0 未決定 B16・B17・B20 | **確定済み**（2026-07-27。16 §B-P0） |
| **B26 物理端末で Expo Go が SDK 54 の企画を開けるか** | **未取得**。B17 から切り出して期限付きで開き直した（本番1章目の凍結前）。シミュレータでしか見ていない |
| 捨て試作を SDK 54 で作り直す | 未着手。本番の1章目を書く前に行う（16 §B-P0） |
| G6 実走検証（`exec`） | **未完走**。共有フックが `npm install` を拒否するため。詳細は `prototype-chapter/道具検証の記録.md` §12 |
| 章2への G4 別ファミリーレビュー | 未実施（1章目のみ実施済み） |
| **B14 カスタム SMTP の要否** | **期限を過ぎている。** 16 は「捨て試作で実測」と決めていたが、捨て試作は完了したのに測っていない。下の「B14 の期限切れ」参照 |
| B群の残り（P1 で決める20件） | Phase 1 の作業。今は着手しない。ほかに B13・B29・B30 が Phase 2 の前まで |

#### B14 の期限切れ（2026-07-28 に発覚）

Supabase が標準で送るメールは1時間に2通までという制限がある。教材では複数アカウントを
作る演習を予定しているので、この上限に当たると演習の途中で手が止まる。
自前のメール送信設定（カスタム SMTP）が要るかどうかは、それを実際に測ってから決める、
と 16 B14 で決めてあった。**測る場所として指定されていたのが捨て試作である。**

捨て試作は 2026-07-27 に完了したが、**メール送信の実測は一度も行っていない**
（`prototype-chapter/` にその実験の記録が無い）。つまり期限を過ぎている。

- 新しい期限: **章分割表を凍結する前**（16 B1）。演習に何アカウント要るかが決まる時点で、
  上限に当たるかどうかが判明していないと章の設計ができない
- 測り方: Supabase の1プロジェクトで連続して登録を行い、何通目から送信が拒否されるかを見る
- これは承認を止めるものではない。Phase 0 の完了条件に入っていない

## 2026-07-26 の構成振り直し（Capacitor + NestJS → Expo + Supabase）

局長決定により技術構成を振り直した。実装コードは1行も存在しないため移行コストはゼロ。
経緯と比較検討は `02_技術選定書.md` §2・§3 が正本。

| 書き直した文書 | 主な変更 |
|---|---|
| 02 技術選定書 | 全面書き直し。Expo vs Capacitor / Supabase vs NestJS構成の比較、既知の限界5件 |
| 00 企画概要 | 「サーバーまで全部自分で作れる」を撤回し、サーバー学習はシリーズ全体で満たす形に |
| 01 要件定義書 | FR1→Supabase Auth / FR9→Realtime / **FR13・FR14・FR15 を追記（再承認が必要）** / 非機能セキュリティを RLS 中心へ |
| 03 基本設計書 | 構成図差し替え。画面 12→16（メール確認待ち／プロフィール初期設定を新設）。UC3（メール確認とディープリンク）新設 |
| 05 DB設計書 | refresh_tokens 削除 / users を auth.users と1対1に / **RLS の節を新設** |
| 09 シリーズロードマップ | 第2弾＝別スタックWeb版、第3弾＝NestJS を正式化。ボツ案を捨てずに移設 |
| 11 ペルソナ・UX | 体験マイルストーンの順序を入れ替え（スマホが最序盤・Web が最終ハイライト） |
| 14 マスターロードマップ | Phase 2 の道具を「既製品4種＋自作2種」に改訂。OpenAPI照合コンパレータ消滅 |
| 15 カリキュラム骨子 | パート構成を作り直し。**章数目安は捨て試作の実測まで空欄** |
| 16 決定バックログ | B群を書き直し（消滅2 / 書き直し5 / 新設2）。C3〜C6 の局長回答を記録 |

**未着手**: 04 / 06 / 08（Phase 1 の着手条件を満たしていないため。10・12・13 は技術非依存のため全面生存）。

## 2026-07-27 に済ませたこと

| 何 | 結果 |
|---|---|
| 捨て試作（`prototype-chapter/`） | 章2本を通しで作り、G3・G5・G6の読み比べ・A7 を実測。**工数を初めて実測（2章目で約28分）** |
| Codex Round 12（スタック変更差分の敵対レビュー） | 13件受領。全件の行き先を 16 の表に固定（本文反映4件 / B17〜B23 起票7件 / 文書直接修正2件） |
| 未コミットだった全成果のコミット | ブランチを `main` へ改称し、意味単位で分割コミット |

## Phase 0: 文書の状態

| 文書 | 状態 | 備考 |
|---|---|---|
| 00_企画概要 | ドラフト・局長レビュー待ち | |
| 01_要件定義書 | ドラフト・局長レビュー待ち | 前提を「単体でも始められる」に改訂済み（2026-07-24局長決定） |
| 02_技術選定書 | ドラフト・局長レビュー待ち | **Expo (React Native) + Supabase**（2026-07-26局長決定で振り直し） |
| 03_基本設計書 | ドラフト・局長レビュー待ち | |
| 04_詳細設計書 | 未着手（Phase 1） | 着手条件: 03承認 |
| 05_DB設計書 | ドラフト・局長レビュー待ち | |
| 06_API設計書 | 未着手（Phase 1） | 着手条件: 03+05承認 |
| 07_開発スケジュール | ドラフト・局長レビュー待ち | |
| 08_テスト計画書 | 未着手（Phase 1） | 着手条件: 04+06確定 |
| 09_教材シリーズロードマップ | ドラフト・局長レビュー待ち | |
| 10_教材制作フロー | ドラフト・局長レビュー待ち | 手戻り16件対応表 |
| 11_ターゲット・ペルソナ・UX定義 | ドラフト・局長レビュー待ち | 売り物兼社内用・単体開始OK反映済み |
| 12_文体・AI臭さ排除方針 | ドラフト・局長レビュー待ち | 局長の既存TS基礎教材（Drive）から文体スペック抽出済み |
| 13_記録・進捗管理規約 | ドラフト・局長レビュー待ち | |
| 14_マスターロードマップ | ドラフト・局長レビュー待ち | |
| 15_カリキュラム骨子案 | ドラフト・局長レビュー待ち | パートA0〜E構成・体験ゴール・退屈対策（2026-07-24追加） |
| 16_決定バックログ | ドラフト・局長レビュー待ち | **未決定事項の唯一の正本**。A群10件確定 / **B群は全30件のうち5件決着・25件が未決定**（内訳: P1 で決める20件／B13 Phase 2 着手時点／B14 期限切れで再設定／B26 本番1章目の凍結前／B29・B30 Phase 2 のゲート実装より前。**期限の無い項目はゼロ**）/ C群は**4件回答済み・2件が「今は判断しない」**（2026-07-28時点。P0 だった B16・B17・B20 は決着済み） |

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
  全11ラウンド・**計97指摘**を処置（反駁0件）。内訳は上の各行の合計
  （32＋20＋16＋9＋5＋3＋3＋3＋3＋2＋1）。以前ここに「92」と書いていたのは足し算の誤り
- Codex Round 12（2026-07-27・スタック変更差分が対象）: CRITICAL 6 / MEDIUM 6 / MINOR 1 → 全13件の
  行き先を確定（台帳: `material/reviews/codex-round12-stack-pivot.md`、対応表は 16 の更新履歴 v6）。
  **Round 11 で合意に達したのは Capacitor + NestJS 前提の文書であり、Expo + Supabase へ
  振り直した差分は別の対象**なので、収束の数え直しが要る。**まだゼロは観測していない**
  （13→次ラウンドの結果が出るまで収束したとは言えない）
- Codex Round 13（2026-07-28・レビューボット処置差分が対象）: CRITICAL 0 / MAJOR 6 / MINOR 2 →
  全8件を処置（台帳: `material/reviews/codex-round13-14.md`）。反駁0件。うち1件は
  **G5 の判定が、片方の章のズレと片方の章の読み取り失敗を取り違える不具合**で、実際に再現させて直した。
  **収束: 13→8。まだゼロは観測していない**（0件を返す回が1度も出ていない）
- Codex Round 14（2026-07-28・Round 13 処置後の差分が対象）: 4件受領。**うち2件は
  受領時点で既に処置済み**（Round 14 が読んだのは1つ前の差分だった）。**新規は2件**。
  1件は **章から引用指示を全部消すと G5 が素通りする**穴（再現させて塞いだ）、
  もう1件は **B13 と C2 に期限が無く、16 自身の A3「タイミングの無い先送りは禁止」に
  反していた**もの。処置後、B群で期限の無い項目はゼロ。
  **収束: 13→8→2。まだゼロは観測していない**
- Codex Round 15（2026-07-28・Round 14 処置後の差分が対象）: 7件受領・**全件成立・全件処置**。
  うち2件は **Round 14 で直したばかりの G5 に残っていた穴**（免除の宣言がコード例の中でも
  効く／存在しない章をズレとして報告する）。G5 の全9経路を走らせて確認した。
  **収束: 13→8→2→7。減ったあと増えた。ゼロは依然として観測していない**
- Codex Round 16（2026-07-28・Round 15 処置後の差分が対象）: 4件受領・**全件成立・全件処置**。
  うち1件は **2ラウンド連続で G5 の同じ関数から出た穴**（囲みの判定が ``` しか見ておらず、
  `~~~` や字下げした囲みで免除を迂回できた）。他3件は、この台帳が自分で定めた
  「未決定の唯一の正本」を自分が破っていたもの（B27・B28・B29 を起票）。
  **収束: 13→8→2→7→4。ゼロは依然として観測していない**
- Codex Round 17（2026-07-28・Round 16 処置後の差分が対象）: 7件受領・**全件成立・全件処置**。
  **G5 の免除判定は3ラウンド連続で迂回された**ため、書式の解析をやめ、免除の宣言を
  章の本文の外（`prototype-chapter/g5-exempt.txt`）へ出して経路ごと消した。
  ほかに、出力なしの異常終了をズレと誤分類する経路、導入案内の版が CI と食い違う点、
  CI 運用の記述が文書間で逆になっていた点、公開後の成功に実行記録が無かった点を処置。
  **収束: 13→8→2→7→4→7。ゼロは依然として観測していない**
- Codex Round 18（2026-07-28・Round 17 処置後の差分が対象）: 3件受領・**全件成立・全件処置**。
  免除簿が名前だけで免除していた点（理由を必須にした）、指定した免除簿が読めない時に
  ズレ側で返っていた点、承認パッケージが Round 17 を落としていた点。
  **収束: 13→8→2→7→4→7→3。ゼロは依然として観測していない**
- Codex Round 19（2026-07-28）: 3件受領・**全件成立・全件処置**。
  免除の仕組みそのものを閉じた（理由さえ書けば照合を外せる状態だった。免除0件なので
  使われた時点で落とす）、終了コード 2 の意味の説明を実態へ合わせた、
  承認パッケージが Round 18 を落としていた点。
  **収束: 13→8→2→7→4→7→3→3。ゼロは依然として観測していない**
- PRレビュー（Round 19 後・2026-07-28）: 4件受領。**2件成立・1件は既に処置済み・1件は反証**。
  成立: 免除簿を章ごとに引いていたため古い行が残り続ける点（簿を丸ごと検査する形へ）、
  `14_マスターロードマップ.md` の Phase 1 完了条件が「05 §4 の6点」のままだった点
  （**14 は工程の正本なので、ここが6点だと後から集約した7点が未解決のまま Phase 1 を
  完了と宣言できてしまう**。13点へ訂正し 16 B8 も合わせた）。
  反証: 壊れた引用指示で PASS が出るという指摘は、3通り試して全部 exit 1（ERROR）だった
- PRレビュー（CodeRabbit・2026-07-28）: 7件受領・**全件成立・全件処置**。
  最も重いのは **`chapter-x.md` から `/dev/zero` へのリンクを置くと grep が終わらず、
  全PRで走る CI ジョブが止まる**という指摘。通常ファイルであることを確かめる形にし、
  実際に止まらないことを確認した。ほかに免除簿の説明が実態と逆だった点、
  API設計の着手条件がDBの未決定と噛み合っていなかった点、記録の強弱の説明が逆だった点など

### この反復をここで一旦止める（2026-07-28）

Round 12〜19 の8周で、指摘は毎回実在し全件処置した。しかし**直近5周の指摘は
`prototype-chapter/tools/g5-quote.sh` に集中している**。このディレクトリは
`10_教材制作フロー.md` §3 が「捨て試作。教材の成果物として一切参照しない」と定めたもので、
Phase 2 で作り直す前提の使い捨ての道具である。

**捨てる予定の道具を磨き続けることと、局長が受け取るべきもの（承認パッケージ）を
出すことは別である。**反復は毎周「N件処置した」という成果の形になるので、
目的から離れたことが成果の形で覆い隠されていた。

よってここで反復を止め、次の判断を局長に仰ぐ。この経緯は
`~/.claude/rules-origins/state-the-goal-before-acting.md` にも記録した。

## 関連リポジトリの作業状態

- task-app/edu-creator: `GENERICIZATION_PLAN.md` を `docs/edu-creator-generalization-plan` ブランチにコミット済み（局長の未コミット作業には未接触）
