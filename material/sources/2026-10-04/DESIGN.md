# Design

## Source of truth

**最新の進行制約（ユーザー指示）: 設計・何を作るか・学習者にどんな体験を届けるかを固めるまで、アプリ機能実装と検証用の新コード作成を進めない。既存コードは候補として保持し、設計の採用根拠にしない。今の作業は設計文書・既存証拠の確認とレビュー。**

- Status: Draft。設計と候補実装をつなぐ索引。原設計・原承認を置き換えず、矛盾した場合はmaterialの原仕様を優先する。
- Last refreshed: 2026-10-04
- 現在の設計判断入口: [SNS教材の設計判断パッケージ](material/decisions/20261004-SNS教材の設計判断パッケージ.md)。体験/章/全画面/資源/証拠/原採否を6束で読む。未採用で原資料を置換しない。Phase0承認記載と01再承認/P1G1は別、C7/C8回答は未回答のまま。
- 保存返答が失われたときの独立比較: [投稿返答喪失と操作照合の設計案](material/decisions/20261004-投稿返答喪失と操作照合の設計案.md)。本人/同じ保存の識別/成功確認、用途限定書込権限、保持とStorage境界、18未実走ケース。公式仕様照合と限定GPT必須0で未採用・未実測。初投稿の章負荷と保持契約を閉じるまで実装開始へ進めない。 削除後のR1/R2/R3保持比較を追加。R2は使用済みkeyを閉じて比較本文を除く優先比較候補で未選択、条件付きRET6/追加限定GPT必須0。完全消去とはしない。
- Primary product surfaces: 学習用SNSモバイルアプリ、日本語対話教材、章の開始snapshotと検証手順。
- Evidence reviewed: material/01_要件定義書.md、03_基本設計書.md、04_詳細設計書.md、05_DB設計書.md、06_API設計書.md、08_テスト計画書.md、10_教材制作フロー.md、12_文体・AI臭さ排除方針.md、18_章分割表.md。
- 過去時点の実装観測（現在の一時worktreeは不存在）: /tmp/sns-trio-ci-review/prototype-chapter/candidates/d4-predecessor/{App.tsx,components/ProfileShell.tsx,lib/profile-flow.mjs,README.md}、d4-heavyの本文/画面図/確認表。既存Expo icon/splashと試作画面図はあるが、完成SNSの承認済み画面・全SNS実機スクリーンショットは今回未確認。
- 体験の具体案: material/decisions/20261003-教材体験と実装開始条件の設計案.md。
- 登録〜初投稿の体験/章別着地/原文同期案: material/decisions/20261003-登録から初投稿までの体験設計案.md。
- 画像〜交流/通知の学習順・資源・削除/購読の具体案: material/decisions/20261003-画像から交流と通知までの体験設計案.md。原同期/採用未決。
- 基礎/検索/非公開保存/Web/説明力の残17章: material/decisions/20261004-基礎から検索Web修了までの体験設計案.md。全体の採用と凍結は未完。
- 次の画像設計: material/decisions/20261003-プロフィール画像と教材前提の設計案.md。未決一覧は16_決定バックログ.mdを正とする。

- 原18の84依存判断（83 B-ID＋C8）の具体比較: material/evidence/20261004-design-remaining-decisions/84-candidate-comparison-index.json。先行33件と残51件を6比較案へ接続。全件候補で採用/実測/原同期/承認は別。C7ほか原台帳とAuth/D4/G6/QA/P1G1の全goalはこの84件より広い。

## 採用提案と開始前の条件（2026-10-04）

- 推奨体験: [学習体験の推奨構成と採用条件](material/decisions/20261004-学習体験の推奨構成と採用条件.md)。32章は第一候補で未確定。31/33章比較、FR全体、原承認を保持する。
- Auth/投稿、交流/検索/検証、章/資源/性能の3採用提案は各28、計84判断。全件未採用であり、原01〜18との正式同期も未適用。
- [採用前条件と独学復帰](material/decisions/20261004-採用前条件と独学復帰の設計.md): 安定Auth buildのWindows/iPhone実行可能性、早期確認HTTPS資源、総メール台帳、画像公開条件、8つの独学復帰、測定と承認の順序を具体化。未測定の待機時間・費用・成立を補わない。
- 原11/18の部分差分は `material/evidence/20261004-design-adoption/proposed-11-18.partial.patch`。一時ディレクトリのみで適用検証。全84原同期やG1承認の代わりにしない。
- 既存QAの歴史的6FAILに対応する現在のselftestsは6/6 PASS。実教材/PDF・全QA・正式G3/G6は別の未達条件。
- 中断後の再開は `material/decisions/20261004-対応版と再開の設計.md` の版/起動→Auth→所有project→直前到達を確認し、対応経路が未成立なら停止する。
- D4は原定義へ再照合し、G1前の教材外本番書式重RLS fixtureの開始PR→G6完走の全工数として計画する。G1後の正式教材章制作まで先送りせず、B50中央値で代替しない。
- Auth署名/learner資源の具体比較: [採用前条件§13](material/decisions/20261004-採用前条件と独学復帰の設計.md)。Windows cloud buildとiPhone install、講師ad hoc登録/更新/枠、無料Mac Personal Team期限、JS/native変更を分離。原B-P0初心者退路/主Mac/Windows未決を保持。公式仕様照合・限定GPT必須0、SIGN8未実走。新節は以前の全体レビュー/packet旧SHAの範囲外で evidence/20261004-auth-signing-design に前後版を保存。
- 全目標の残件は `material/evidence/20261004-design-adoption/full-goal-current-audit.md` を参照。設計freeze=false、implementation_ready=falseを維持する。

## 実装へ進む前の設計完成条件（2026-10-04）

1. **何を作るか**: 対象者・FR1〜15の完成時機能・非対象・各章で見せる機能範囲を、原要件と全画面へ対応させる。
2. **どう学ぶか**: 各章の開始状態・変更・観測・説明課題・復帰が一つの体験としてつながり、手順完走だけを理解の証拠にしない。
3. **開始してよいか**: 全画面とDB/API受入条件が対応し、Auth/署名/保持/拒否後再開などの未決を原台帳上の具体的な採否として閉じる。

現時点はいずれも未完。文言だけの限定レビュー0件を、設計freeze/実装開始/正式G6へ置き換えない。ユーザーの最新指示に従い、実装より先にこの設計を固める。

## Brand

- Personality: 初学者に具体的な操作と観測結果を伝える日本語。架空の習熟や失敗を作らない。
- Trust signals: 保存済み値と入力中の値を区別し、成功・拒否・結果不明を観測根拠に合わせる。
- Avoid: 100点保証、未収集エラーを0件扱い、準備中の画面を完成機能として提示。

## Product goals

- Goals: FR1〜FR15を原スコープの章順に実装し、未経験〜初級インターンが開始snapshotと本文から再現できる教材を作る。
- Non-goals: DM、広告、通報・自動モデレーション、動画変換、多言語、OSプッシュ（01§2）。
- Success signals: アプリの実挙動、章本文と開始状態の一致、原ゲートの実走証拠。候補unit/CIの成功は正式ゲートの代わりにならない。

- 学習体験と理解の評価候補: [学習体験と修了判断の設計案](material/decisions/20261004-学習体験と修了判断の設計案.md)。原31章を8段階へ接続し、予想→小さな変更→現物確認→説明・復帰の課題を提案。原12の7要素/FR1〜15を保持。未採用で、課題確認を正式G6や実装開始の根拠にしない。

## Personas and jobs

- Primary personas: 教材利用者は未経験〜初級のインターンと独学購入者（11§2）。アプリ内の想定利用者は投稿・閲覧・交流したい一般利用者（01§1）。
- User jobs: 本人プロフィールを編集、投稿と交流、通知を見る。学習者は段階ごとに作成・拒否・回復を理解する。
- Key contexts: モバイル主体。経験者のスキップ導線は11_ターゲット・ペルソナ・UX定義.mdに従い、今回は再設計しない。

## Information architecture

- Primary navigation: 認証→プロフィール初期設定→SNS本体。復帰リンクのrecovery経路は通常編集と分離。
- Core screens: 04§1.2の画面表を正とする。過去候補はprofile-setup/profile/profile-edit/timeline-placeholder。候補の仮タイムラインは採用未決。途中章の着地は登録〜初投稿の体験案で設計し、章170までは同章で作った確認欄/プロフィール等へ戻す。画面総数は未決を維持。
- Content hierarchy: 章の目的→開始状態→操作→観測→拒否時の回復→章末確認。画像はパートBのプロフィールと画像投稿、パートCカメラで同経路を再利用（06§5.4）。

## Design principles

- 保存完了は本人・対象とその操作の結果を確認できる読取に基づいて表示する。post id未受領時の同じ本文は1件でも候補に留め、今回の保存の証明にしない。輸送失敗では失敗・成功を断定せず、結果不明から保存済み状態を確認できる。
- 原設計と候補コード・教材・検証行列でバケット名と更新列を揃える。
- Tradeoffs: 画像のStorageとDB更新は別操作。単純なUIのために二段階失敗を隠さず、回復経路の費用を設計比較へ含める。

## Visual language

- Color: 現在候補のReact Native既存StyleSheetを暫定再利用。完成アプリのブランド色は未承認。
- Typography: 日本語UIと読みやすい端末標準書体。具体的サイズ/拡大時レイアウトは実機検証前に合意・記録する。
- Spacing/layout: 入力・保存・再読込・戻るのまとまりを分ける。
- Shape/elevation: 新しいデザインシステムを追加せず、既存部品を使う。
- Motion: 状態確認に不要な演出は追加しない。
- Imagery: アバターとヘッダーの別用途。未設定時の見せ方、切抜き比率・alt相当のラベルは未決として明示。

## Components

- Reuse: Auth form/return処理、ProfileShell、プロフィールrepository、既存StyleSheet。
- Changed components: 画像選択・preview・保存状態・再確認・回収状態の部品は設計案段階、未実装。
- States: 初期読込、未作成、入力中、保存中、重複、0行、結果不明、再読込済み。画像固有状態は設計案で定義。
- Ownership: 原仕様material、候補コード隔離worktree、制作証拠material/evidence。HTMLは私有一時レビューのみ。

## Accessibility

- Target: 01の基本キーボード・コントラスト配慮を維持。具体的WCAG適合レベルは未決、取得済みとは主張しない。
- Keyboard/focus: 読込・失敗・戻る後のfocus復帰を端末で検証する。
- Contrast/readability: 色だけで保存状態を伝えず、文言と操作可否を併記。
- Screen reader: 入力と操作にラベル。状態読み上げと画像用途を新UIで検証。
- Reduced motion: 演出が必要になったら端末設定に従う。

## Responsive behavior

- Devices: iOS/Androidモバイル（原仕様）。iPhone12miniの過去限定試験は、新profile画面の証拠へ転用しない。
- Adaptations: キーボード表示、文字拡大、小画面で保存・取消・回復が届くことを確認。
- Touch/hover: hover前提の操作を作らない。タッチ領域の具体値は端末評価に記録する。

## Interaction states

- Loading: 何を読込中かを表示し、同じmutationの重複を止める。
- Empty: 未作成プロフィールを空の保存フォームに見せない。
- Error: 重複・列権限・0行・輸送失敗を区別。raw payload/tokenを表示しない。
- Success: 保存済み値の再読込一致後。画像ではDB保存確認と画像読込状態を分ける。bytes/hashは制作側の受入証拠にする。
- Disabled: 保存中や認証変更中は競合する操作を無効にする。
- Offline/slow: timeout=未保存とは限らない。再確認が済む前に画像を自動削除しない（設計案）。

## Content voice

- 教材本文は磯貝）/阿部）の対話形式、発話間の空行、先生3文以内など12を正とする。
- UIは短い日本語。入力破棄を先に知らせる。実装内部名を利用者の操作案内へ露出させない。
- 未測定、未収集、未準備、拒否、結果不明を混同しない。架空の生徒の実体験を作らない。

## Implementation constraints

- Expo/Supabaseを原技術構成として維持。SDK57は候補、原承認状態は変更しない。service_roleをアプリへ渡さない。
- Storageは原設計avatars/post-media。profile-avatars/profile-headersは確認表の誤記であり、新バケット方針として採用しない。
- 画像をStorageへ送る形式は04§1.3/B104が未決。React Nativeのblobで0byte問題があるため既存Web fetchの例をそのまま転用しない。新依存は無断追加しない。
- 観測と性能目標は08/B23の条件へ結びつける。固定時間で全部の端末に成功を保証しない。
- テストの将来順: 体験/機能/章/受入条件の設計を固める→所有local資源だけのSDK/DB検証→新sourceの実機UI/故障→START/正式read/exec。CI greenだけでは後二つを代替しない。

## Open questions

- [ ] U12/B21: 公開範囲とサーバー側MIME・容量。原設計担当＋実測担当。読取経路・教材説明に影響。
- [ ] U21/U19/B66: URL書戻し/導出、許可列、固定名とcache。設計担当。DB/API/Storage/章コードへ同時反映。
- [ ] U13: 孤児画像の回収方式。設計担当。プロフィール案だけで投稿削除の方針まで閉じない。
- [ ] B24/B25/B64: username必須/未設定表示/updated_at担当。原未決を維持。
- [ ] 全SNS画面のbrand・token・画像比率・focus/screen reader・実機完了条件。設計担当。今回の暫定候補で凍結しない。
- [ ] 正式START、7役割実ログ、plain/minus、G6 read/exec、外部Auth、C7/C8、P1/G1。制作・原承認担当。goalはactive。

## DB13の具体契約（2026-10-04）

[DB13と画面API受入の同期案](material/decisions/20261004-DB13と画面API受入の同期案.md)に原13件を学習者結果/画面/DB/API/受入へ接続。全件未採用、原変更未適用。画像の途中不可視と全rollback、通知の過去履歴保持/再操作/本人既読/他人拒否を具体化。独立GPT限定再検査0、外部三者合意/実測/原承認ではない。05部分差分は索引追記だけで全schema同期ではない。

## 主要画面状態の本文候補（2026-10-04）

[主要画面の状態とDB13受入差分](material/decisions/20261004-主要画面の状態とDB13受入差分.md): 6グループの正常/失敗/保持/本人変更/不明結果/旧応答/削除/通知を04/06/08本文候補へ接続。原session管理と生秘密入力を区別。operation照合はB19だけでは成立せず、別の未採用契約の原台帳起票候補を保持。独立GPT限定再検査0、全IA/SQL同期/実測/原承認/三者合意ではない。

## 原31章の理解・復帰課題の候補（2026-10-04）

[原31章の理解と復帰課題の割当案](material/decisions/20261004-原31章の理解と復帰課題の割当案.md): 各章の概念導入後の変更、要素5説明、要素7転用、開始資源/復帰を具体化。原31章のID/前章/最初の結果/未決依存を保持。100/110/120の通常権限対照時点、users公開read、自己follow採否、210追加D資源を未採用分岐として明示。11/12/18/08部分差分は未適用で、原同期完了/実理解/正式G6/実装開始ではない。

## 全画面の入口・移動・復帰候補（2026-10-04）

[全画面と復帰の設計案](material/decisions/20261004-SNS全体の画面と復帰の設計案.md): 原04表の全16行の入口/操作/失敗/本人/章境界と34移動条件を具体化。16は表行で画面総数未決。既存6状態契約と31章課題を保持した04/06/08統合部分差分は未適用。限定GPT0と条件付き静的到達/差分再現は実走/SQL同期/原採用/設計凍結を証明しない。

## 登録・初投稿・復帰の画面文言候補（2026-10-04）

[登録初投稿と復帰の画面案](material/decisions/20261004-登録初投稿と復帰の画面案.md): 3journey/26状態の未採用案。Droid実Gemini 3.8 Flash/Opus 5.5 medium第20回、独立GPT。現行26状態の文言/guardに限り三者必須0・限定合意。原140論理削除/260camera保持。AUTH08/16継続確認不可の離脱/logout、AUTH11未成立離脱、AUTH14権限拒否後、B14/B88再開、POST03/04照合未成立後の新規作成、R1等対象利用不可の結果表示/再開、OP/RET保持/破棄は未完。設計全体/原採用/実UX/正式G6/100点/全goal/実装開始の合格ではない。次は原31章・全画面・DB13を通し学習体験として照合する。詳細範囲はentry-screen-design/latest-external-review.json。

## 章ごとの開始・終了・復帰の比較（2026-10-04）

[章境界と開始終了復帰の比較案](material/decisions/20261004-章境界と開始終了復帰の比較案.md)で、原31章の開始資源・最初の成果・終了状態・復帰先を対応させた。A31/B32/C32/D33は110分割と本人投稿一覧145分離の二軸候補。原終了文と候補要約、FRと原04依存node、判断IDと変更対象原文を分離。作者の静的確認はID・前章鎖・原文保持・hashに限定し、学習者体験の成立を証明しない。Phase0承認を維持し、候補改訂・実snapshot・比較実測・原同期・正式G1は未完。実装開始へ進めない。

この章境界資料の独立GPT必須1（150の原未決への候補混入）は修正済み。再レビューは限定必須0で全31原未決ID一致を確認。章境界の実UX・採用・正式G1や、他の設計文書の外部合意を証明しない。

## 学習者の連続経路とDB13/FR接続（2026-10-04）

[学習の連続性と画面データ条件の接続案](material/decisions/20261004-学習の連続性と画面データ条件の接続案.md)を章境界・課題の最新補完として読む。AB生成、負例対象と次章へ渡す対象、120の保存値確認着地、80/120/200/210入口、学習者L3/L6と局長C8の分離を具体化した。既存資料の曖昧な持越しや120 timeline着地はこの未採用候補と原変更対象として区別する。原資料を置換しない。DB13全13原番号/原文/判断ID/必要証拠とFR15件を章と画面へ対応。通知契機と200導入、130 profile画像と150投稿画像、160 followsと170 timelineを分ける。独立GPT旧5件→現行限定0。Droid実Gemini 3.8 Flash/Opus 5.5 medium第5回も同一版に限定必須0。章単位G6と本人160→170持越しの前後照合を分け、原D4重い1章の全工数条件を保持。版/hash/receipt/未完はlearning-continuity/latest-external-review.json。AB/保持/画像/資源/理解確認の採否、実測、全原同期と正式G1は未完、implementation_ready=false。

## メール待ちと相手役準備の負担（2026-10-04）

[メール需要と相手役準備の設計案](material/decisions/20261004-メール需要と相手役準備の設計案.md): 原19項/13suite/6準備種を名前付き目的へ接続。送信要求開始状態、準備instance、観測消費、到達/リンク完了、費用/実作業/待機を分ける。共通準備を複数章から参照しても重複加算しない。未帰属消費/未知網羅性/メールなし準備も保持。110比較resetで210受入を代用しない。旧採用前条件§3のcharged確定条件/集計式改訂は原担当採用待ちの候補差分。Droid実Gemini 3.8 Flash/Opus 5.5 medium第3回と独立GPTは同一版に限定必須0。原採用/N1〜N5/物理Auth/原同期/実UX/P1G1は未完。implementation_ready=false、全goalを維持する。

## Auth資源と各受入の同一版接続（2026-10-04）

[設計判断パッケージ](material/decisions/20261004-SNS教材の設計判断パッケージ.md)の追加節へ、署名・本人/相手役・メール・確認/resetの条件をbinding/run/stageで接続した。原H7待機とB103回復、H8native画面/端末別3枝/元スマホ復帰、B88全write、B95二責務、凍結route/plan/hash、予定と実event集合・件数・retry・順序を区別。実Droid Gemini/Opus 5.5 medium第5回と独立GPTは同一版の追加節限定必須0。auth-resource-binding/latest-external-review.jsonに版/receipt/限定範囲。実資源/runは空、全体採用/実UX/原同期/AuthD4G6QAP1G1/実装開始の合格ではない。次は未完の画面guardと章別離脱/再開を閉じる。

## 全体設計案への取りまとめ（2026-10-04）

既存設計判断パッケージの「全体設計の取りまとめ v7」を現在の候補入口とする。B32推奨/原31章の一本の流れ、4主要入口と章別有効化、標準書体・余白・画像比率・contrast/focus候補、EXIT-01〜07/RESUME-01/RESULT-01/CLOSED-01、保持/中断/local logoutの区別をまとめた。上の旧26状態「未完」欄は新候補の出口へ接続したが、原採用・実装・実測・設計凍結は未完。過去の限定レビューは旧snapshotの履歴で現行全体案へ外挿しない。

見た目の候補は本文16/見出し24、余白4/8/16/24、touch領域iOS 44pt/Android 48dp/Web WCAG 2.2比較、通常contrast4.5:1以上。unit/端末標準部品/拡大時適用は採用版で確認し、認証済み適合や全OS成立を主張しない。navはtimeline/search/notification/profileの4入口を完成SNSの第一候補とし、未導入機能を早期章で有効化しない。

全体v6はpreUID Auth記録と本人付き保存記録を分け、platform/文字/画像別の保持・消失、120のreadとwrite診断、確認済み対象不可と不明結果の保留を具体化した。RESUME-01/RESULT-01/CLOSED-01は追加3候補で基礎26状態を改数しない。旧unknownを失敗にせず、独立新intentは原OP-13との保証差がある比較代案へ分け、第一候補では未知結果から新送信へ戻さない。未採番の起票候補は関連B-ID/原主体/P1G1前/導入章/原同期/必要実測に接続する。原採用・実装開始・全goal完了とはしない。

全体v6のWREC-01は120 profile/140投稿のtyped操作登録・本人履歴・同key明示再試行・lock内中止確定の追加比較候補。投稿未到達とclient記録喪失をread-onlyで解消したと約束しない。Web logoutは私的入力除去を第一候補とし、UI隔離を同browser profileへの秘匿と混同しない。採用/費用/章負荷/SQL/API/保持実測は未完。

WREC-01は全許可保存経路の同lock/不可逆terminal状態を採用条件にし、予約再作成/遅延要求の迂回を許さない。保存receiptはDB変更と原子的、Storage別結果。非秘密Auth入力も実読可能時だけ保持済みを案内する。

全体v6ではWREC予約操作のpending終了をserver terminal確認へ同期し、確定拒否のclosure commit失敗もunknownとして維持する。元入力の有無はretry可否だけを決めfenceを制限しない。現在値表示と旧保存成功を分け、無条件の入力保持文言は排他的なactual-read条件案内へ置換する。

全体v6の3追加候補にCLOSED01を含める。terminal reason=user_cancelled/rejectedをunknownより先に分類し、post拒否POST07/profile拒否AUTH14/本人中止CLOSED01へ着地。入力/oldkeyを次操作へ自動継承しない。AUTH05のnative見出しと成功/現在値variantを同期。

全体v6はprofileのtrusted保存成功と現在users読取不能を分けてAUTH16成功variantへ着地し、当該pendingのみterminal条件で終了する。現在read失敗を保存不明へ巻き戻さない。JSON自己記述とnative/DESIGNは基礎26＋追加3を同期する。

## 候補v7の分岐同期

保存前確認補足v2の5差分を候補の画面JSON/Markdownと全体WREC契約へ反映。正常本人server履歴はlocal未送信/通常章より先、未確認予約/登録不明はPOST03/AUTH11、網羅性不明は新保存停止。AUTH04/POST02はtrusted terminal先行、拒否rollbackだけで終了しない。local未dispatchを全経路未開始とせず、login transport不明は用途別EXIT07とAuth状態guardを分ける。これは原04/05/06/08/11/18への正式同期・採用・実装/実測ではなく候補内の同期。旧レビューは各snapshot限定、v7の実装開始/原承認/全goal/100点を保証しない。

候補v7の新key作成はnew_mutation_entry_contractで入口ごとに履歴網羅性/未確認なしとserver側の原子的admission・予約確認を要する。同key続行/既知結果/active待ちは別。復帰表から結果を表示できても新保存の許可にはしない。これは全new-key writer/競合/排他の追加WREC採用・測定条件であり既存APIや実装ではない。

候補v7の予約phaseはsubmit時に固定する。PROFILE01/POST05/CLOSED01/RESULT01の新規入力選択は空欄の入力画面へ移るだけでkey/予約/admissionを作らない。POST01/AUTH04で本人がsubmitを選び、入力/画像/revisionをfreezeした後に当該keyの原子的admission/予約を一度確認し、その後の同key保存へ。登録不明phaseを経た遅延応答や再起動からは自動保存せず、同key明示続行でstateを再確認する。予約前の入力不存在を新しいreserved/draft phaseで埋めず、既存WRECのstate数を増やさない。原採用/実装/実測は未完。
