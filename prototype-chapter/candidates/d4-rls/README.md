# D4 RLS 前段候補

> **NON_FORMAL_D4_PREDECESSOR_CANDIDATE**
> これは `material/05_DB設計書.md` と `material/06_API設計書.md` を実測へ進めるための候補です。正式な D4 契約、局長承認済みスキーマ、G6 の凍結入力ではありません。

## 収録物

- `supabase/migrations/20261003080326_d4_predecessor_candidate.sql`: Supabase CLI 2.119.0で作成。9テーブル、外部キー、索引、RLS、GRANT、Authプロフィールトリガーの初回候補。
- `supabase/migrations/20261003081350_d4_remove_unneeded_parent_definer.sql`: 直接相関EXISTSの実測に基づき、不要な親確認definerを除去。
- `supabase/migrations/20261003081937_d4_align_notification_update_visibility.sql`: UPDATEにも通知の可視条件を適用し、フィルタなしSQLでの隠れた通知更新を拒否。

各ファイルはCLIの `migration new` で作った履歴を保持します。適用済みSQLを書き換えず、追加変更を別のマイグレーションへ記録します。

適用対象は、所有者が明示した専用のローカル検証スタックだけです。このディレクトリ単体では `db reset`、共有DBへの適用、本番適用、StorageやRealtimeの設定を行いません。

## 05 / 06 と同じ形

- テーブルは `users`, `posts`, `post_media`, `likes`, `follows`, `notifications`, `hashtags`, `post_hashtags`, `bookmarks` の9本です。
- `users.id` は `auth.users.id` と1対1で、登録後トリガーは `id` だけを入れます。利用者メタデータは信用しません。
- `users.username` と `display_name`、`posts.body` はNULL可です。
- `posts.reply_to_post_id` と `repost_of_post_id` は `posts.id` への自己参照です。
- 通知種別は現在の設計書どおり `like`, `reply`, `follow`, `repost` の4値です。
- UUIDと、05で既定値が明記されていない日時には既定値を追加していません。B19をこの候補で決めないためです。
- 外部キーの削除動作は設計書に指定がないため、PostgreSQL既定の `NO ACTION` のままです。

## 実測用に固定した暫定選択

以下は候補内で一貫した挙動を測るための選択で、B27 / U19 / U20 の正式決定ではありません。

1. 削除済み投稿は `posts` だけでなく、`post_media`, `likes`, `post_hashtags`, 本人の `bookmarks`, 投稿に紐づく `notifications` からもDB側で隠します。投稿を持たないフォロー通知は表示対象です。
2. 削除がコミット済みの投稿へのリプライ、リポスト、いいね、ブックマーク、画像・タグの追加を、非並行の実行で拒否します。並行する削除と追加の直列化は保証していません。
3. 投稿は作成後に直接UPDATEできません。本人が呼べる `public.soft_delete_post(uuid)` だけが `deleted_at` を設定します。物理DELETEは許可しません。
4. `users` は `username`, `display_name`, `bio`, `avatar_url`, `header_url` だけ更新可能です。`created_at` と `updated_at` はクライアントから更新できません。
5. `notifications` は本人が `read_at` だけ更新できます。INSERT / DELETEは公開しません。
6. 未ログインの `anon` には9テーブルと候補RPCの権限を与えません。

RLSを回避する必要がある処理は `private` スキーマへ置き、`search_path = ''` と完全修飾名を使っています。最初のマイグレーションの親投稿確認helperは、2本目で削除します。現在の単純なSELECTポリシーでは直接の相関EXISTSでもINSERTが動くことを、PostgreSQL17.11のロール切替トランザクションで確認しロールバックしました。最終状態の `security definer` はAuthプロフィール作成と本人所有投稿の論理削除だけです。論理削除は関数内でも `auth.uid()` と `author_id` を照合し、`PUBLIC` と `anon` のEXECUTEを取り消します。公開RPCは `security invoker` の薄い入口です。

## 元設計との差分と未決

- 05のB27は未決ですが、この候補では親投稿と子行をDBで隠す側を選びました。
- 06のU19は未決ですが、この候補では列単位GRANTと専用論理削除RPCを併用しました。これを正式案として採用した扱いにはしません。
- 06のU20は未決ですが、この候補では、削除がコミット済みで非並行の実行時に、削除済み親への子書き込みを拒否します。
- `post_media.order` は元の列名を保ち、SQLでは常に引用します。最大4枚をDBでどう保証するかは05 §4課題2のまま残し、この候補ではCHECKやトリガーを推測で追加していません。
- 空投稿、リプライとリポストの同時指定、自己フォロー、タグ正規化、通知生成トリガー、通知種別追加、検索方式、Storage、Realtime、メール確認済み条件は未決のままです。候補SQLは推測で決めていません。
- B19に従い、クライアント作成行のUUID・日時の投入主体は未決です。`users.created_at/updated_at` と `posts.created_at` だけは05に書かれた既定値を保持しています。
- `users.updated_at` をプロフィール更新時に誰が変更するかはB64のままです。この候補は利用者による直接更新だけを列権限で拒否し、未承認の自動更新トリガーは追加していません。
- 正式Auth、外部メール、Phase 0のゲート、B27/U19/U20、G6入力凍結はこの候補では完了しません。

## 適用前後の境界

適用前に、対象が専用ローカルスタックであること、9テーブル名、関数のEXECUTE権限、`anon` の無権限、SQL全文をレビューします。適用後の受入には少なくとも次が必要です。

- 実ユーザーJWTを2人分使い、本人の成功と他人の拒否を各操作で測る。
- 削除済み親と子行のSELECT不可、削除済み親への全対象INSERT不可を測る。
- 投稿の直接UPDATE/DELETE不可と、本人RPCだけ成功することを測る。
- `users` と `notifications` の許可外列が列権限で拒否されることを測る。
- `anon`、未確認メール、Realtime、Storageは別の受入条件として扱い、結果を混ぜない。
- `supabase db advisors` とマイグレーション履歴を確認する。

リセットは専用ローカルスタックの再現に限ります。共有スタック、リモートプロジェクト、本番データを対象にするリセット手順はここには置きません。

## 実測で分かった限定条件

- 適用前の専用DBはpublicにtrial_postsだけで、privateスキーマと同名Authトリガーは存在しませんでした。既存private関数を上書きできる一般移行ツールとして扱いません。適用には同じ事前確認が必要です。
- 既存Authユーザーを一括backfillしません。受入では移行後に新しく作成したA/Bを使います。既存ユーザーのprofile欠落は別の移行課題です。
- 既定NO ACTION外部キーを持つため、Authユーザーの個別削除を後片付けに使いません。試験行は専用スタック内で保存し、供給側の所有行限定resetが実装・検証されるまで正式開始状態は凍結しません。
- 削除済み投稿のいいね・ブックマークは本人のDELETEでも0行で、物理行が残りました。解除機能やカウント仕様を完了したと扱いません。DELETEポリシーだけを緩めてもSELECT側で非表示になる条件を無視できません。
- 削除済み投稿に紐づく通知のread_at UPDATE＋selectは0行で、管理側でもread_atは変わりませんでした。投稿なしのフォロー通知は表示されました。通知は管理側の試験seedで、生成トリガーの実装ではありません。
- RLSの文スナップショットには並行性の限界があります。2つのPostgreSQLロール切替セッションで、論理削除を未コミットにした間にリプライといいねを追加し、その後削除をコミットすると両方の子行が残りました。通常SDK経路の証明ではなく、制御したDB競合の実測です。既存リプライ・リポスト自身の行は親の削除では隠れません。
- profilesのURL安全性、子メディア/タグの編集許可、任意read_at、未確認/匿名Auth、全DB13、メール・Storage・Realtime、B27/U19/U20の採否は未完了です。

`app/` はAuth候補の追跡対象19ソースだけを引き継ぎ、RlsTrialを追加した終了状態の参照実装です。依存キャッシュ・ビルド出力は複製していません。正式D4の学習開始状態や、章だけから初回成功まで実行した証拠ではありません。

3本目適用前の制御SQLロール試験では、WHERE/RETURNINGのないread_at更新が非表示の通知も変更しました（ROLLBACKで復元）。3本目適用後は同じ操作でも非表示の通知は不変で、表示可能なフォロー通知だけが更新されました。このDBロール試験と通常SDKのフィルタ付き試験を区別します。

## 所有行の準備と片付け

`reset_owned.py`は制作側専用で、今回の相異なるA/Bとrun IDをstdinから受け取り、合成投稿を2件だけ準備します。`--reset`はその2件だけを対象にし、manifest外の参照があれば非破壊で停止します。Auth、profile、子行、共有投稿は削除しません。

所有記録は環境変数のHOMEではなくpasswdのhomeから解決する`~/.local/state/sns-d4-owned-runs`へ保存します。所有dirは0700、filesは0600で、symlink・所有者・既存衝突を検査し、排他的作成とfsyncを使います。既存の親dirの権限は変更しません。実際のWSL再起動試験は行っていません。

`reconcile_owned.py`は固定ローカルDBをread-onlyで照合し、absent/seeded/partial/conflictを区別します。古いsourceの記録を自動承認しません。`migrate_owned_manifest.py`はレビュー済みの旧sourceだけを許可し、DB状態とA/Bを確認して永続領域へ明示移行します。旧ファイルは変更せず、元bytesと移行receiptを別のprivate filesへ残します。DB書き換え、Auth削除、自動修復は行いません。

transaction advisory lockは各準備・reset・照合トランザクションの範囲です。UIの全実行期間を覆うleaseではなく、現在の試走は制作側の運用で直列化しています。正式A5、全run lease、汎用seed/reset、START凍結の受入は別途必要です。
