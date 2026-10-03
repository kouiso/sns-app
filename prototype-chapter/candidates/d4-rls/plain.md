# RLSで「見える」と「変更できる」を分ける plain版

**NON_FORMAL_D4_HEAVY_CHAPTER_CANDIDATE_PLAIN**

<!-- 抜いた要素: 対話 -->

この文書は、D4重い章候補から対話を除いた比較稿です。操作、期待結果、証拠の境界は本文と同じであり、正式なD4開始やG6合格を表しません。

## 到達点

通常の利用者A/Bで同じ検証用投稿を開き、次を確認します。

| 順番 | 到達点 |
|---|---|
| 1 | AにはAさんとBさんの投稿が見えます。 |
| 2 | BがAの投稿へ論理削除RPCを実行すると、boolean `false`になり、DB状態は変わりません。 |
| 3 | Aが自分の投稿へ同じRPCを実行すると、boolean `true`になり、一覧から消えます。 |
| 4 | 制作担当が、論理削除後も物理行が残ることをDBで照合します。 |

## 開始条件

候補環境では、制作側がAuth、3本のmigrationを適用した9テーブル、別々の確認済みアカウントA/B、A/Bそれぞれの検証用投稿を準備済みです。公開接続情報、検証用投稿2件のID、A/Bのサインイン情報は実行時に渡します。

学習者はDocker、Supabase CLI、管理キー、DB passwordを使いません。実際のURL、キー、メールアドレス、passwordも教材へ記載しません。

## 今回扱う範囲

| 場所 | 確かめること | 今回は扱わないこと |
|---|---|---|
| Auth | A/Bの通常サインイン | 管理APIによる利用者作成 |
| 投稿一覧 | 今回の実行で使う投稿2件を読む | 検索、無限スクロール |
| 投稿の変更 | 所有者だけが限定RPCで論理削除する | 任意UPDATE、物理DELETE |
| 証拠 | 画面、RPC、制作担当のDB照合 | 画面だけによるDB状態の断定 |

プロフィール、フォロー、通知を含むSNS全体の完成は範囲外です。

## 権限とRLS

`GRANT`は操作の入口を開き、RLS policyは対象行を絞ります。期待する操作には両方が必要です。

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

`USING`は既存行を操作する際の対象条件です。`WITH CHECK`はINSERTやUPDATE後の行が条件内かを検査します。

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

実際のpolicyはリポスト元も同じ条件で検査します。`posts`のクライアント権限はSELECTとINSERTだけで、作成後の変更は論理削除RPCへ限定されます。

## 起動と投稿一覧

前章から使っているSDK 57アプリを起動してください。

```bash
cd prototype-chapter/candidates/d4-rls/app
npm run start
```

公開接続情報や検証用投稿のIDが欠けている場合は、値を推測せずrunを停止してください。投稿IDと作成日時には制作側seedの発行値を使います。

アプリは環境に設定された2件の投稿IDだけを取得します。並び順は作成日時の降順、同じ日時ではIDの昇順です。

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

Aでサインインすると、`Aさんが作った投稿`と`Bさんが作った投稿`が並ぶ想定です。各行には`自分の投稿`または`他の人の投稿`と、`論理削除を試す`ボタンが表示されます。

## 論理削除RPC

`posts`にはクライアント向けのUPDATE権限がありません。非公開schemaの関数だけを`SECURITY DEFINER`にし、所有者を照合して`deleted_at`を書き換えます。

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

`search_path`は空に固定されています。対象は`auth.uid()`が所有する未削除の投稿だけで、更新行が1件なら`true`、0件なら`false`です。

公開する関数は`SECURITY INVOKER`の薄い窓口で、認証済み利用者だけが実行できます。権限が必要な更新を非公開関数に閉じ込め、外から呼ぶ入口と分けています。

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

## Bによる他者投稿の操作

| 順番 | 操作 |
|---|---|
| 1 | Aからサインアウトします。 |
| 2 | Bでサインインします。 |
| 3 | `Aさんが作った投稿`の`論理削除を試す`を一度押します。 |
| 4 | `他の人の投稿、または削除済みの投稿は変更しませんでした`が出ることを確認します。 |

RPCがboolean `false`を返した場合だけ、この文言を表示します。HTTP 200は通信成立を示しますが、行の変更成功は示しません。

実装は`error`、boolean以外、`false`の順で判定します。次の抜粋は最後の`false`分岐だけを説明するもので、そのまま貼り付けるコードではありません。

```ts
if (data === false) {
  setActionMessage(
    '他の人の投稿、または削除済みの投稿は変更しませんでした',
  );
  return;
}
```

`error`が空でも、`data`が`null`なら成功にしません。`true`と`false`以外は結果不明として扱います。

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

## Aによる所有投稿の操作

| 順番 | 操作 |
|---|---|
| 1 | Bからサインアウトします。 |
| 2 | Aでサインインします。 |
| 3 | `Aさんが作った投稿`の`論理削除を試す`を一度押します。 |
| 4 | `投稿を非表示にしました`が出ることを確認します。 |
| 5 | 一覧更新後にAの投稿が消えることを確認します。 |

RPCの想定結果は、最初の呼び出しが`true`、同じ投稿への2回目が`false`です。制作担当が、`deleted_at`が入り、物理行が残ることをDBで照合します。

## 最初に確認する結果

| 証拠 | 確認する値 | 確認方法 |
|---|---|---|
| Aの画面 | `Aさんが作った投稿`と`自分の投稿` | Aで通常サインインした画面 |
| Bの画面 | 他者投稿の変更なしを示す正確な文言 | Bで通常サインインした画面 |
| RPC | HTTP 200、boolean `false` | RPCの応答 |
| DB | Aの行が1件、`deleted_at is null` | 制作担当のDB照合 |

画面、RPC、制作担当のDB照合の3つがそろった時点を最初の結果とします。3種類の結果を照らし合わせます。

画面の世代管理、15秒timeout、unmount時の中断は表示の揺れを抑える補助であり、RLSの成立条件ではありません。

## 確認問題

| 番号 | 問題 |
|---|---|
| 1 | `GRANT`、`USING`、`WITH CHECK`の役割を、それぞれ一文で説明してください。 |
| 2 | BがAの投稿へ論理削除RPCを2回実行した場合のbooleanとDB状態を予想してください。 |
| 3 | Aが自分の投稿へ論理削除RPCを2回実行した場合に、結果が変わる理由を説明してください。 |
| 4 | `data`が`null`で`error`が空の場合に、成功表示を出さない理由を説明してください。 |

解答は別掲です。

## 制作メモ: source provenance

この節は制作側の記録です。source hashの機械可読版は[SOURCE-MANIFEST.json](./SOURCE-MANIFEST.json)へ固定します。

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
| 候補環境 | Auth、9テーブル、新規作成した確認済みA/B、制作側所有の投稿2件があります。永続所有記録の安全ユニットテスト15件、実DBのseed/reset 12項目、移行8項目、read-only照合5項目を通過しています。 |
| formal A5 | 開始入力は未凍結です。`EXPO_PUBLIC_RLS_TRIAL_POST_IDS`は、相異なるUUIDをちょうど2件、カンマ区切りで渡す公開設定です。 |
| 一覧の安定性 | `RlsTrial`は対象IDを2件に絞り、`created_at`降順、`id`昇順で並べます。requestは15秒で中断し、unmount時も未完了requestを中断します。 |
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
| SDKのfilterなしUPDATE | HTTP 400、PostgreSQL code `21000`で拒否されました。プロフィールと通知の観測は制作側の回帰検査です。 |
| 並行操作 | 親投稿の削除と子行の追加を並行させると、子行が残るケースを実測しました。この候補は運用上の直列runだけを扱います。 |

## 制作メモ: 未完了の判定

正式な章執筆開始、formal A5、D4、G6、完成SNSはすべて未達です。独立read 2ラウンド、軽い章と重い章それぞれ3回の最初の画面結果、中央値、正式START source、run全体のleaseが残っています。

実装PRや章の開始時刻は過去へ遡って付けません。現在の原稿、SDK 69/69、seed/reset検査を正式合格へ読み替えません。
