# v7の原反映差分と実測開始条件

作成: 2026-10-04T04:08:30.346307+00:00。設計案の未適用差分。原採用/実装可能/測定済み/全目標完了はいずれもfalse。

## 原文に反映する変更

章全体やDB/APIの完全差分ではない。以下6箇所は、原文の現在hashと実在するアンカーを束縛した変更対象。原稿は編集していない。

### AUTH-ROUTE — material/04_詳細設計書.md:945
原アンカー: ### 9.3 セッションの状態は3値である

§7.1・§9.3・§9.4を同時改訂。Auth三値を保ち、ログイン中→無条件タイムラインという表示を、owner/project・目的・未確認操作・既知結果・初期設定の順序を評価する画面選択へ置換。購読数と復帰判断を区別する。

### AUTH-LINK — material/08_テスト計画書.md:307
原アンカー: | H7 | 別の端末でリンクを開いたとき | PC のメールで同じリンクを開く | ブラウザが開く。**アプリ側の画面は待ったまま**になる（04 §1.4 の経路 b） | 復帰経路が設計に無い【04 §1.4 で起票済み】 | **B18** |

H6/H7/H8/H9/H10/H11に確認/reset目的とUID前記録を接続。別端末のメール確認が、現在端末のsession成立を意味するという期待を置かない。cold/warm、期限・再利用・別owner・通信不明の最終画面と認証状態を別証拠にする。

### MUTATION — material/06_API設計書.md:986
原アンカー: ### 6.3 ★ 最も重要な1点 — 拒否は「エラー」として返るとは限らない

影響行数確認の既存規則を維持し、WREC採用時は「errorなし/1行/現在値一致」と当該操作のtrusted successを分離。profile_save/post_saveのowner/project/keyとterminal証拠を追記する。公開関数名/引数/権限/lock順序は未設計のため、原06単独で確定しない。

### DB13 — material/05_DB設計書.md:183
原アンカー: ## 4. 既知の未解決課題（Codex R1 M22 — Phase 1で解消するまで本書は「過不足なくカバー」を名乗らない）

全13項目を残したまま、operation台帳/receipt/同key排他・新key admission/保持と消去を追加設計対象に起票する。DB13索引の追記だけで13件を解消しない。原03/05が確定してから06を凍結する原順序を守る。

### CHAPTER — material/18_章分割表.md:56
原アンカー: | text-post | 140 | B | 文章を投稿する | posts と同章の RLS を作り、280字以内の投稿を投稿詳細で確認できる | profile-view-and-edit | - | 未着手 |  | 投稿作成,投稿詳細 | screen | 予定節: 投稿した文章が詳細に出る（未実測） | B1,B63,B68,B71,B72,B76,B86,B91,B115 |

140/145候補/150/120/130の画面・開始終了・DB/API・受入を同時改訂。入力画面へ移るだけではkey生成/予約なし。submitで入力固定後に一度だけadmission/予約、以後は同key明示続行。145は既存本人投稿を探す章で、150新規保存の許可の代わりにはならない。

### G6 — material/10_教材制作フロー.md:470
原アンカー: - **G6 教材実走検証（新設 — 局長の危惧 2026-07-24 への直接対策）**:

原execの非執筆・文脈ゼロ・教材とstarterのみ、read4体×2roundsの各3/4条件を維持。Read限定CLIや今回の文書照合をG6へ代入しない。plain/minusは既存真正logから作り、R2 N/Aは高価値0のcount/hash証拠に限る。

## 実測へ進むための未完了条件

| 測定 | 必要な開始材料 | 終了を証明するもの | 現状 |
| --- | --- | --- | --- |
| Auth | 採用対象SDK/HEAD・所有hosted project・通常本人A/B・宛先・署名/build/許可redirect・メール需要台帳と上限・reset・秘密値を含めない記録方法 | 実外部受信からリンク操作、cold/warm/別端末/再起動、確認とreset各目的、最終session/画面/当該保存状態のreceipt | 旧controlled/Mailpitは参照のみ。正式外部経路未完 |
| D4 | G1前の教材外・本番書式重RLS fixture。実在開始PR/HEAD、対象schema/seed/accounts/reset、時計と担当、原章ルール・真正開発log | PR開始→制作/G3–G6終了の全工数。人作業/モデル/待機/失敗/画像/対照版を同runへ束縛 | 69SDK項目等の前提証拠は全工数でない。未開始 |
| G6 exec/read | 完成fixture・starter・許可入力hash。非執筆文脈ゼロの実行体、host/HOME/source/networkの否定到達証拠と独立判定。read4体と真正plain/minus | execの完走と全欠落trace、read各round3/4以上、退屈改訂の記録、N/Aなら高価値0のcount/hash | 今回のnative lookupもG6でない |

## 採用時に混同しないもの

- 表示IDの空き照会/名前取り置きとWREC operation予約は別契約。B97の名前予約代案そのものはv7との矛盾ではない。補助照会を保存admissionの証拠にしない。
- 直接DMLは一律拒否を確定していない。通常権限を含む全保存経路を同じ規律に統一するか、迂回権限を閉じる具体案を原03/05/06へ返す。
- DB terminalとStorage bytesの存在/回収を別に記録。DB rollbackやfence成功だけで画像不存在とはしない。
- 旧partial patchは章/UX/DB13索引のみ。v7の予約・trusted terminal条件を含む完成パッチへ昇格しない。

## 今回の証拠修正

entry-screen-designのv20レビューは当時の26状態版限定。現行native/JSONは別hashのため、旧manifestの最新合意trueをfalseへ修正し、最新索引をwhole-designへ向けた。旧原本はwhole-design内に保存。旧レビュー結果は削除せず、現行三者合意へ流用しない。

Droid枠は前回確認のまま。再呼び出し・課金・認証・SSH・端末/build・送信・SQL・新検証code・公開は実行していない。残12要件はfull-goal-current-audit.mdのまま未達。
