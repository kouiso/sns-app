# RLSで「見える」と「変更できる」を分ける

**NON_FORMAL_D4_HEAVY_CHAPTER_CANDIDATE**

磯貝）前章では、Supabase Authで通常の利用者としてサインインできるところまで進めました。この章では、そのセッションで投稿を読み、変更できる投稿が利用者ごとに違うことを確かめます。

阿部）削除できない投稿なら、ボタンを隠せばよいのではありませんか。

磯貝）画面だけで制限すると、別のクライアントから同じ操作を送れます。今回はボタンを表示したまま操作し、データベースが返す結果を確認しましょう。

磯貝）制作側は、Auth、9テーブル、確認済みの通常アカウントA/B、AさんとBさんの検証用投稿を準備済みです。学習者はDocker、管理キー、DB passwordを使いません。

阿部）サインイン情報は教材に書かれていますか。

磯貝）実値は書きません。実行時に渡されたA/Bのサインイン情報と、設定済みの公開接続情報を使います。

> この章は正式版ではない候補です。通常アカウントA/Bと、今回の実行で使う投稿ID2件が準備された環境で使います。

## 今回扱う範囲

| 場所 | 確かめること | 今回は扱わないこと |
|---|---|---|
| Auth | A/Bが別々の通常利用者としてサインインする | 管理APIによる利用者作成 |
| 投稿一覧 | 今回の実行で使う投稿2件を読む | 検索、無限スクロール |
| 投稿の変更 | 所有者だけが限定RPCで論理削除する | 任意UPDATE、物理DELETE |
| 証拠 | 画面、RPC結果、制作担当のDB照合を分ける | 画面だけでDB状態を断定すること |

磯貝）完成品ではプロフィール、フォロー、通知も同じ境界の上に載ります。この章は投稿一覧と論理削除に範囲を絞ります。

阿部）この章を終えれば、SNS全体が完成しますか。

磯貝）まだ完成ではありません。ここで身につけるのは、「画面に見える」と「変更できる」を分けて確かめる方法です。

## 権限とRLSを分けて読む

磯貝）SQLでは、テーブル権限とRLS policyの両方を通る必要があります。`GRANT`が操作の入口を開き、policyが対象行を絞ります。

```sql
grant select on table public.posts to authenticated;
grant insert (
  id,
  author_id,
  body,
  reply_to_post_id,
  repost_of_post_id
) on table public.posts to authenticated;

create policy posts_select_active
  on public.posts for select to authenticated
  using (deleted_at is null);
```

阿部）`posts`にはUPDATEやDELETEの`GRANT`がありません。

磯貝）そのとおりです。投稿作成後の任意UPDATEは公開せず、論理削除だけを専用RPCへ通します。

磯貝）`USING`は既存行を操作するときの対象条件です。`WITH CHECK`はINSERTやUPDATEの結果としてできる行を検査します。

```sql
create policy posts_insert_own_with_active_parents
  on public.posts for insert to authenticated
  with check (
    (select auth.uid()) = author_id
    and deleted_at is null
    and (
      reply_to_post_id is null
      or exists (
        select 1 from public.posts as parent
        where parent.id = posts.reply_to_post_id
          and parent.deleted_at is null
      )
    )
  );
```

磯貝）実際のpolicyはリポスト元も同じ条件で検査します。自分の投稿として作ることと、削除されていない投稿だけを参照先にすることを確認しています。

## アプリを起動する

磯貝）前章から使っているSDK 57アプリを起動します。公開接続情報と検証用投稿2件のIDは、制作側が環境へ設定済みです。

```bash
cd prototype-chapter/candidates/d4-rls/app
npm run start
```

磯貝）設定が欠けている場合、画面は検証用投稿を読みません。URLや投稿IDを推測して補わないでください。

阿部）投稿IDや作成日時は自分で決めますか。

磯貝）決めません。制作側のseed処理が発行した値を使います。

## 今回の投稿だけを読む

磯貝）アプリは、環境に設定された2件の投稿IDだけを取得します。作成日時の降順で並べ、同じ日時ならIDの昇順にします。

```ts
const { data, error } = await client
  .from('posts')
  .select('id,author_id,body,created_at')
  .is('deleted_at', null)
  .in('id', trialPostIds)
  .order('created_at', { ascending: false })
  .order('id', { ascending: true })
  .limit(20)
  .abortSignal(controller.signal);
```

磯貝）Aでサインインすると、`Aさんが作った投稿`と`Bさんが作った投稿`が並ぶ想定です。各行には`自分の投稿`または`他の人の投稿`と、`論理削除を試す`ボタンが表示されます。

阿部）前の実行で残った投稿があっても、この2件だけを見られるんですね。

磯貝）はい。画面に表示する範囲は、制作側から渡された2件のIDに限られます。

## GRANTがなくても限定RPCが更新できる理由

阿部）`posts`にUPDATE権限がないのに、RPCはどうやって`deleted_at`を書き換えるのですか。

磯貝）非公開schemaの関数だけを`SECURITY DEFINER`にし、その中で所有者を確認します。`search_path`を空に固定し、対象を`auth.uid()`が所有する未削除の投稿だけに絞っています。

```sql
create or replace function private.soft_delete_owned_post(p_post_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  affected_rows integer;
begin
  if (select auth.uid()) is null then
    return false;
  end if;

  update public.posts
  set deleted_at = now()
  where id = p_post_id
    and author_id = (select auth.uid())
    and deleted_at is null;

  get diagnostics affected_rows = row_count;
  return affected_rows = 1;
end;
$$;
```

磯貝）公開する`soft_delete_post`は`SECURITY INVOKER`の薄い窓口で、認証済み利用者だけが実行できます。権限が必要な更新を非公開関数に閉じ込め、外から呼ぶ入口と分けています。

磯貝）非公開関数は、更新行が1件なら`true`、0件なら`false`を返します。

```sql
create or replace function public.soft_delete_post(p_post_id uuid)
returns boolean
language sql
security invoker
set search_path = ''
as $$
  select private.soft_delete_owned_post(p_post_id);
$$;
```

## BからAの投稿を変更してみる

磯貝）Aからサインアウトし、Bでサインインします。`Aさんが作った投稿`の`論理削除を試す`を一度押してください。

阿部）Bは所有者ではないので、どんな結果になるはずですか。

磯貝）RPCがboolean `false`を返し、`他の人の投稿、または削除済みの投稿は変更しませんでした`と表示される想定です。HTTP 200でも、`false`なら変更成功ではありません。

磯貝）実装は`error`、boolean以外、`false`の順で判定します。次の抜粋は最後の`false`分岐だけを説明するもので、そのまま貼り付けるコードではありません。

```ts
if (data === false) {
  setActionMessage(
    '他の人の投稿、または削除済みの投稿は変更しませんでした',
  );
  return;
}
```

阿部）`error`が空なら、`data`が`null`でも成功にしてよいですか。

磯貝）成功にはしません。`true`と`false`以外は結果不明として、一覧とDB状態を確認します。

```ts
if (error) {
  setActionMessage(
    '変更結果を確認できませんでした。通信を確認して投稿一覧を更新してください。',
  );
  return;
}
if (data !== true && data !== false) {
  setActionMessage(
    '削除結果を確認できませんでした。投稿一覧を更新して状態を確認してください。',
  );
  return;
}
```

## Aが自分の投稿を非表示にする

磯貝）BからサインアウトしてAへ戻り、`Aさんが作った投稿`の`論理削除を試す`を押します。RPCが`true`なら、`投稿を非表示にしました`と表示され、一覧の更新後にその投稿が消える想定です。

阿部）一覧から消えたら、行そのものがDELETEされたと考えてよいですか。

磯貝）論理削除なので、行そのものは残ります。今回は制作担当がデータベースを確認し、画面の見え方と照らし合わせます。

阿部）同じ投稿でもう一度RPCを呼んだらどうなりますか。

磯貝）すでに`deleted_at`が入っているため、更新行は0件になり`false`です。所有者であることだけでは、2回目の更新は成功しません。

## 最初に確認する結果

磯貝）最初にそろえる結果は3つです。Aの所有投稿が見えること、Bが同じ投稿を変更できず正確な文言が出ること、制作担当のDB確認で未変更と分かることです。

| 証拠 | 確認する値 | 確認方法 |
|---|---|---|
| Aの画面 | `Aさんが作った投稿`と`自分の投稿` | Aで通常サインインした画面 |
| Bの画面 | 他者投稿の変更なしを示す正確な文言 | Bで通常サインインした画面 |
| RPC | HTTP 200、boolean `false` | RPCの応答 |
| DB | Aの行が1件、`deleted_at is null` | 制作担当のDB照合 |

磯貝）画面、RPC、DBの1つだけで判断しないことが大切です。3種類の結果を照らし合わせます。

## よくある疑問

阿部）Bがボタンを2回押したら、2回目はエラーになりますか。

磯貝）対象は最初からBの所有物ではないので、どちらも`false`です。通信エラーが起きた場合はbooleanを推測しません。

阿部）Aが同じ投稿で2回押した場合はどうなりますか。

磯貝）最初は`true`、削除済みになった後の2回目は`false`です。戻り値は、今回1件を更新したかを表します。

阿部）画面の世代管理や中断処理も、RLSに必要ですか。

磯貝）RLSの成立条件ではありません。古い応答や連打で検証画面の表示が揺れないようにする補助コードです。

## まとめ

阿部）テーブル権限とRLS policyは役割が違い、操作には両方が関わります。論理削除は専用RPCへ通し、非公開関数が所有者と未削除状態を確認します。

阿部）HTTP 200でもboolean `false`なら変更成功ではありません。画面から消えた場合も、物理DELETEと決めつけず制作担当のDB照合と分けて考えます。

磯貝）整理できています。UIの表示とデータベースの許可を分けて確認できれば、保護の根拠を見失いません。

## 演習

1. `GRANT`、`USING`、`WITH CHECK`の役割を、それぞれ一文で説明してください。
2. BがAの投稿へ論理削除RPCを2回実行したときのbooleanとDB状態を予想してください。
3. Aが自分の投稿へ論理削除RPCを2回実行したとき、結果が違う理由を説明してください。
4. `data`が`null`で`error`が空の場合に、成功表示を出してはいけない理由を書いてください。

解答は別掲です。

## 制作メモ: source provenance

この節は制作側の記録であり、学習者の操作ではありません。source hashの機械可読版は[SOURCE-MANIFEST.json](./SOURCE-MANIFEST.json)へ固定します。

| ソース | SHA-256 |
|---|---|
| `supabase/migrations/20261003080326_d4_predecessor_candidate.sql` | `e4667d31b9beff022b56a030ef4f0c26f924224c1170b2285bdda823d2c109b4` |
| `supabase/migrations/20261003081350_d4_remove_unneeded_parent_definer.sql` | `5684db307ec7f1cf873032465fa9cbb9f7f14dd264effbbd509792a51c2795c4` |
| `supabase/migrations/20261003081937_d4_align_notification_update_visibility.sql` | `b493ec015eaf4f98a1ddb453ceb839caa232ee17b6043cfe3b7cc0cef5f75f7b` |
| `app/App.tsx` | `a6a3f0f7bddc989d47cda970c98406f41f65270b9ad795cabecf16c122644904` |
| `app/components/RlsTrial.tsx` | `bb545fb408b491fea9b20bd0a345f91eb1a4596893e23faacdee9ef7ed904961` |

## 制作メモ: 前提と実測

| 項目 | 制作側の記録 |
|---|---|
| 候補環境 | Auth、3本のmigrationを適用した9テーブル、新規作成した確認済みA/B、制作側所有の投稿2件があります。永続所有記録の安全ユニットテスト15件、実DBのseed/reset 12項目、移行8項目、read-only照合5項目を通過しています。 |
| formal A5 | 開始入力は未凍結です。`EXPO_PUBLIC_RLS_TRIAL_POST_IDS`は、制作側が発行した相異なるUUIDをちょうど2件、カンマ区切りで渡し、runの投稿を識別します。 |
| 一覧の安定性 | `RlsTrial`は2件のIDでSELECTを絞り、`created_at`降順、`id`昇順で並べます。requestは15秒で中断し、unmount時も未完了requestを中断します。 |
| 実機run v1/v2 | 起動とログインの前提がそろわず失敗し、合格証拠には採用していません。1Passwordで通常サインインを済ませた専用Expo homeを用意し、その場所を`__UNSAFE_EXPO_HOME_DIRECTORY`で指定して起動経路を修正しました。 |
| 実機run v3 | 13/14項目を通過しましたが、reload commandが失敗しました。実reloadの証拠には採用していません。 |
| 実機run v4 | 制御された通常経路で15/15項目を通過しました。AppとRlsTrialのsource hashは表の値から変わっていません。 |
| reloadと復元 | Metro protocol v2で実reload commandを送り、実機側API read countの増加を独立確認しました。復元後はAの投稿がhidden、Bの投稿がvisibleでした。 |
| 後片付け | 通常sign-outと制作側が所有する投稿のresetを確認しました。 |
| 実機run v6の故障試験 | 未転送のRPCと、DB更新済み・応答保留のRPCを別々に測り、通常系と合わせ25/25項目を通過しました。結果不明の文言、ボタンの回復、DB実状態、手動再取得、後片付けを照合しました。 |
| timeoutの切り分け | proxyの応答を60秒保留し、未転送21.240秒、応答保留20.815秒のWDA込み観測で結果不明と操作回復を確認しました。20秒保留のv5は中断と503応答の切り分けが不十分なため、最終timeout証拠には使いません。 |
| 未測定の失敗経路 | UI concurrencyを含む全失敗経路の実機検査は完了していません。実WSL再起動、停電直後の記録耐久性も証明していません。 |
| 直列化 | `reset_owned.py`のtransaction advisory lockはseed/reset中だけ有効で、UI操作の前に終了します。現在はleaderの運用でUI runを直列化し、run全体のlease実装は未完了です。 |
| reset/reconcile | resetのsource hashは`6d01cba56da854ccb43ba747a74c1e5b70024004ec09f93f7c29a4de53c8e517`で、reconcileはこれを照合するread-only toolです。所有記録はpasswd homeの`~/.local/state/sns-d4-owned-runs`へ保存し、旧bytesは明示移行で保持します。 |

## 制作メモ: SDKとDBの観測

| 観測 | 結果 |
|---|---|
| fresh SDK | 3本のmigrationを含む69/69項目が通り、catalogのbefore/afterも一致しました。証拠の適用範囲は候補スキーマまでで、正式D4とG6の状態は未達のままです。 |
| DB roleのfilterなしUPDATE | 3本目のmigration前はhidden通知の`read_at`が変わりました。適用後はhidden通知が不変となり、表示可能なfollow通知だけが変わりました。 |
| SDKのfilterなしUPDATE | HTTP 400、PostgreSQL code `21000`で拒否されました。プロフィールと通知の観測は制作側の回帰検査で、学習者向けFAQや演習には含めません。 |
| 並行操作 | 親投稿の削除と子行の追加を並行させると、子行が残るケースを実測しました。本章候補は運用上の直列runだけを扱い、並行安全性を主張しません。 |

## 制作メモ: 未完了の判定

正式な章執筆開始、formal A5、D4、G6、完成SNSはすべて未達です。独立read 2ラウンド、軽い章と重い章それぞれ3回の最初の画面結果、中央値、正式START source、run全体のleaseが残っています。

実装PRや章の開始時刻は過去へ遡って付けません。現在の原稿、SDK 69/69、seed/reset検査を正式合格へ読み替えません。
