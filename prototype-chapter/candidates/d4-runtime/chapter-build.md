# 投稿画面を前章のアプリへ組み込む

磯貝）この章では、前章で作った認証アプリに投稿一覧を加えます。通常アカウントAとBで同じ2件を表示し、他人の投稿を変更できないことと、自分の投稿だけを論理削除できることを確かめます。

阿部）削除ボタンを隠さず、押した結果で権限を確かめるんですね。

磯貝）はい。画面はどちらの投稿にも同じボタンを出します。変更を許可するかどうかは、データベース側が判断します。

## 開始状態を確認する

この章までの教材と、開始フォルダにあるAuthアプリを使います。教材外のファイルは参照しないでください。

通常アカウントAとBには、それぞれ投稿が1件ずつ用意されています。公開接続情報と投稿2件のIDは、宣言された入力経路から制作側が渡します。学習者は管理キー、Docker、DB passwordを使いません。

実機用Metro、Expoログイン、接続経路も制作側が準備します。接続情報が足りないときは、URLやキーを推測せずに作業を止めます。

阿部）開始時に投稿が見えていたら、そのまま進めますか。

磯貝）開始状態が違うので止めます。最初はサインイン後に「SNS のプロフィール機能は次の実装範囲です」と表示され、投稿画面は存在しないことを確認します。

## 投稿画面のファイルを作る

開始フォルダをエディターで開き、直下に`components`フォルダを作ります。その中へ`RlsTrial.tsx`を作ってください。

以下の15ブロックを、番号順に連結して1つのファイルへ保存します。ブロックの見出しやコードフェンスはファイルへ入れません。

磯貝）短く区切っていますが、別々のプログラムではありません。コード1の先頭からコード15の末尾まで、続けて保存してください。

### コード 1

```tsx
import type { SupabaseClient } from '@supabase/supabase-js';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Button, StyleSheet, Text, View } from 'react-native';

const trialPostIds: readonly string[] = String(process.env.EXPO_PUBLIC_RLS_TRIAL_POST_IDS ?? '')
  .split(',').map((value) => value.trim().toLowerCase());
const hasTrialPostIds = trialPostIds.length === 2
  && new Set(trialPostIds).size === 2
  && trialPostIds.every((id) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id));

type PostRow = Readonly<{
  id: string;
  author_id: string;
  body: string | null;
  created_at: string;
}>;

type Operation = Readonly<{
  token: symbol;
  generation: number;
}>;

export type RlsTrialProps = Readonly<{
```

### コード 2

```tsx
  client: SupabaseClient;
  userId: string;
}>;

function isPostRow(value: unknown): value is PostRow {
  if (!value || typeof value !== 'object') return false;
  const row = value as Record<string, unknown>;
  return (
    typeof row.id === 'string' &&
    typeof row.author_id === 'string' &&
    (row.body === null || typeof row.body === 'string') &&
    typeof row.created_at === 'string'
  );
}

export function RlsTrial({ client, userId }: RlsTrialProps) {
  const [posts, setPosts] = useState<readonly PostRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyPostId, setBusyPostId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [freshnessMessage, setFreshnessMessage] = useState<string | null>(null);
  const generationRef = useRef(0);
  const mountedRef = useRef(false);
```

### コード 3

```tsx
  const operationRef = useRef<Operation | null>(null);
  const refreshRef = useRef<Operation | null>(null);
  const controllersRef = useRef(new Set<AbortController>());

  const isCurrent = useCallback(
    (generation: number) => mountedRef.current && generationRef.current === generation,
    [],
  );

  const refreshPosts = useCallback(
    async (generation: number) => {
      if (!isCurrent(generation) || refreshRef.current) return false;
      if (!hasTrialPostIds) {
        setLoading(false);
        setFreshnessMessage('検証用の投稿が設定されていません。制作側の準備を確認してください。');
        return false;
      }
      const refresh = Object.freeze({ token: Symbol('refresh'), generation });
      refreshRef.current = refresh;
      setLoading(true);
      const controller = new AbortController();
      controllersRef.current.add(controller);
      const timeout = setTimeout(() => controller.abort(), 15_000);
```

### コード 4

```tsx
      try {
        const { data, error } = await client
          .from('posts')
          .select('id,author_id,body,created_at')
          .is('deleted_at', null)
          .in('id', trialPostIds)
          .order('created_at', { ascending: false })
          .order('id', { ascending: true })
          .limit(20)
          .abortSignal(controller.signal);

        if (!isCurrent(generation)) return false;
        if (
          error ||
          !Array.isArray(data) ||
          data.length > 20 ||
          !data.every(isPostRow)
        ) {
          setFreshnessMessage(
            '最新の投稿一覧を取得できませんでした。表示中の内容は更新されていません。',
          );
          return false;
        }
```

### コード 5

```tsx

        setPosts(data);
        setFreshnessMessage(null);
        return true;
      } catch {
        if (!isCurrent(generation)) return false;
        setFreshnessMessage(
          '最新の投稿一覧を取得できませんでした。表示中の内容は更新されていません。',
        );
        return false;
      } finally {
        clearTimeout(timeout);
        controllersRef.current.delete(controller);
        if (
          isCurrent(generation) &&
          refreshRef.current?.token === refresh.token
        ) {
          refreshRef.current = null;
          setLoading(false);
        }
      }
    },
    [client, isCurrent],
```

### コード 6

```tsx
  );

  useEffect(() => {
    mountedRef.current = true;
    const generation = ++generationRef.current;
    operationRef.current = null;
    refreshRef.current = null;
    setBusyPostId(null);
    setActionMessage(null);
    setFreshnessMessage(null);
    setPosts([]);
    void refreshPosts(generation);

    return () => {
      if (generationRef.current === generation) generationRef.current += 1;
      mountedRef.current = false;
      for (const controller of controllersRef.current) controller.abort();
      controllersRef.current.clear();
      operationRef.current = null;
      refreshRef.current = null;
    };
  }, [client, refreshPosts, userId]);

```

### コード 7

```tsx
  const softDelete = useCallback(
    async (postId: string) => {
      if (operationRef.current || refreshRef.current || !mountedRef.current) return;
      const operation = Object.freeze({
        token: Symbol('soft-delete'),
        generation: generationRef.current,
      });
      operationRef.current = operation;
      setBusyPostId(postId);
      setActionMessage(null);
      const controller = new AbortController();
      controllersRef.current.add(controller);
      const timeout = setTimeout(() => controller.abort(), 15_000);

      try {
        const { data, error } = await client.rpc('soft_delete_post', {
          p_post_id: postId,
        }).abortSignal(controller.signal);
        if (!isCurrent(operation.generation)) return;

        if (error) {
          setActionMessage(
            '変更結果を確認できませんでした。通信を確認して投稿一覧を更新してください。',
```

### コード 8

```tsx
          );
          return;
        }
        if (data !== true && data !== false) {
          setActionMessage(
            '削除結果を確認できませんでした。投稿一覧を更新して状態を確認してください。',
          );
          return;
        }
        if (data === false) {
          setActionMessage(
            '他の人の投稿、または削除済みの投稿は変更しませんでした',
          );
          return;
        }

        setActionMessage('投稿を非表示にしました');
        await refreshPosts(operation.generation);
      } catch {
        if (!isCurrent(operation.generation)) return;
        setActionMessage(
          '変更結果を確認できませんでした。通信を確認して投稿一覧を更新してください。',
        );
```

### コード 9

```tsx
      } finally {
        clearTimeout(timeout);
        controllersRef.current.delete(controller);
        if (
          isCurrent(operation.generation) &&
          operationRef.current?.token === operation.token
        ) {
          operationRef.current = null;
          setBusyPostId(null);
        }
      }
    },
    [client, isCurrent, refreshPosts],
  );

  const retry = useCallback(() => {
    if (operationRef.current || refreshRef.current || loading) return;
    void refreshPosts(generationRef.current);
  }, [loading, refreshPosts]);

  return (
    <View style={styles.container} testID="rls-trial">
      <Text style={styles.title}>RLS の動作確認</Text>
```

### コード 10

```tsx
      <Text style={styles.caption}>
        この試行のために準備した2つの投稿を表示しています。
      </Text>

      <Button
        title="投稿一覧を更新"
        onPress={retry}
        disabled={busyPostId !== null || loading}
        testID="rls-refresh-button"
      />

      {actionMessage ? (
        <Text style={styles.actionMessage} testID="rls-action-message">
          {actionMessage}
        </Text>
      ) : null}

      {freshnessMessage ? (
        <View style={styles.notice} testID="rls-list-unable-fresh">
          <Text style={styles.errorMessage}>{freshnessMessage}</Text>
          <Button
            title="投稿一覧をもう一度読み込む"
            onPress={retry}
```

### コード 11

```tsx
            disabled={busyPostId !== null || loading}
            testID="rls-retry-button"
          />
        </View>
      ) : null}

      {loading ? (
        <View style={styles.loading} testID="rls-posts-loading">
          <ActivityIndicator />
          <Text style={styles.loadingText}>投稿一覧を更新しています</Text>
        </View>
      ) : null}

      {!loading && posts.length === 0 && !freshnessMessage ? (
        <Text style={styles.empty} testID="rls-posts-empty">
          表示できる投稿はありません。
        </Text>
      ) : null}

      {posts.map((post) => {
        const isOwnPost = post.author_id === userId;
        return (
          <View key={post.id} style={styles.post} testID={`rls-post-row-${post.id}`}>
```

### コード 12

```tsx
            <Text style={styles.ownerLabel}>
              {isOwnPost ? '自分の投稿' : '他の人の投稿'}
            </Text>
            <Text style={styles.body}>{post.body?.match(/^d4-owned-run:[0-9a-f]{16,64}:actor-([ab])$/)
              ? (post.body.endsWith(':actor-a') ? 'Aさんが作った投稿' : 'Bさんが作った投稿')
              : (post.body ?? '（本文なし）')}</Text>
            <Button
              title="論理削除を試す"
              onPress={() => void softDelete(post.id)}
              disabled={busyPostId !== null || loading}
              testID={`rls-soft-delete-${post.id}`}
            />
            {busyPostId === post.id ? (
              <Text style={styles.busyText}>変更できる投稿か確認しています</Text>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
```

### コード 13

```tsx
  container: {
    gap: 12,
    paddingVertical: 16,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
  },
  caption: {
    color: '#475569',
    lineHeight: 21,
  },
  actionMessage: {
    backgroundColor: '#ecfeff',
    borderColor: '#0e7490',
    borderRadius: 8,
    borderWidth: 1,
    color: '#164e63',
    padding: 12,
  },
  notice: {
    backgroundColor: '#fff7ed',
    borderColor: '#c2410c',
```

### コード 14

```tsx
    borderRadius: 8,
    borderWidth: 1,
    gap: 8,
    padding: 12,
  },
  errorMessage: {
    color: '#9a3412',
    lineHeight: 21,
  },
  loading: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  loadingText: {
    color: '#475569',
  },
  empty: {
    color: '#475569',
    paddingVertical: 16,
    textAlign: 'center',
  },
  post: {
```

### コード 15

```tsx
    backgroundColor: '#ffffff',
    borderColor: '#cbd5e1',
    borderRadius: 10,
    borderWidth: 1,
    gap: 10,
    padding: 14,
  },
  ownerLabel: {
    color: '#334155',
    fontSize: 13,
    fontWeight: '700',
  },
  body: {
    color: '#0f172a',
    fontSize: 16,
    lineHeight: 23,
  },
  busyText: {
    color: '#475569',
    fontSize: 13,
    textAlign: 'center',
  },
});
```

## コードの流れをつかむ

磯貝）コードは長く見えますが、追う場所は5つです。

コード1は、制作側から渡された投稿IDが異なる2つのUUIDかを確認します。

コード4は、その2件のうち`deleted_at`が空の投稿だけを読みます。

コード3〜9は、通信中の二重操作を止め、利用者が切り替わった後に古い応答を画面へ反映しないようにします。

コード7〜9は、投稿IDを`soft_delete_post`へ渡し、応答を`true`、`false`、確認不能の3通りに分けます。

コード10〜12は、どちらの投稿にも削除ボタンを出します。所有者の判定はRPCとRLSに任せます。

阿部）他の人の投稿にもボタンがあるのは、作り忘れではないんですね。

磯貝）はい。ボタンを隠すだけでは権限制御になりません。同じ操作を送り、データベースが他人の変更を拒むことを画面で確かめます。

### RPCの3つの結果

| RPCの結果 | 分かること | 次の操作 |
| --- | --- | --- |
| `true` | 自分が所有する未削除の投稿を変更できた | 一覧を読み直し、対象が表示されなくなったことを確認する |
| `false` | RPCは正常に終わったが、変更できる行は0件だった | 他人の投稿か、すでに削除済みの投稿として扱う |
| エラー、タイムアウト、`true/false`以外 | 変更されたかどうかを確認できない | 成功とも未変更とも決めず、通信を戻して一覧を更新する |

`false`は通信失敗ではありません。サーバーまで処理が届き、変更対象がなかったことを表します。

`true`の後で一覧の再取得だけが失敗する場合もあります。このとき、RPCの成功まで取り消されたわけではありません。成功の文言と一覧を更新できなかった文言が同時に出たら、もう一度一覧を更新します。

一覧から投稿が消えたことで分かるのは、有効な投稿の一覧にその投稿が返らなくなったことです。画面の観察だけで、データベース内部の更新内容までは断定しません。

## サインイン後の画面につなぐ

`App.tsx`のimport群へ次の1行を追加します。

```tsx
import { RlsTrial } from './components/RlsTrial';
```

次に、`sessionState === 'signed_in'`の中にある`recoveryUserId`の分岐を探します。パスワード再設定側の`TextInput`や保存ボタンには触れません。

置換前は、分岐の末尾が次の形です。

```tsx
          ) : (
            <Text style={styles.body}>メール確認済みのセッションです。SNS のプロフィール機能は次の実装範囲です。</Text>
          )}
```

この3行だけを、次の5行へ置き換えます。

```tsx
          ) : (
            userId
              ? <RlsTrial key={userId} client={client} userId={userId} />
              : <Text style={styles.body}>ログイン状態をもう一度確認してください。</Text>
          )}
```

阿部）`key`に利用者IDを渡すのは、なぜですか。

磯貝）AからBへ切り替えたとき、前の利用者の画面状態を持ち越さないためです。サインインの処理とパスワード再設定は、前章のコードを引き続き使います。

通常サインイン時の外側の見出しは、開始アプリの「プロフィール準備中」のままです。この章では、この見出しは変更しません。権限確認の結果は、その下に表示される「RLS の動作確認」で読み取ります。

## 型を検査する

開始フォルダのターミナルで型を確認します。依存の追加や固定ファイルの変更はありません。

```bash
npm run typecheck
```

エラーが出たら、15ブロックの順番、importの位置、`App.tsx`で置き換えた範囲を確認します。

## A、B、Aの順に試す

### 1. Aで2件を確認する

通常アカウントAでサインインします。「Aさんが作った投稿」が「自分の投稿」、「Bさんが作った投稿」が「他の人の投稿」と表示されることを確認してください。

### 2. BでAの投稿を試す

ログアウトし、通常アカウントBでサインインします。「Aさんが作った投稿」の「論理削除を試す」を押してください。

「他の人の投稿、または削除済みの投稿は変更しませんでした」と表示され、Aの投稿が一覧に残れば、`false`の経路を確認できています。RPCは正常に終わりましたが、Bが変更できる行はありませんでした。

### 3. Aで自分の投稿を試す

ログアウトし、もう一度Aでサインインします。「Aさんが作った投稿」の「論理削除を試す」を押してください。

「投稿を非表示にしました」と表示され、一覧の再取得後にAの投稿が見えなくなれば、`true`の経路を確認できています。Bの投稿は引き続き表示されます。

この操作の後は、Aの投稿がこの画面から見えなくなります。章を最初からやり直すときは、同じ投稿を使い回さず、制作側にアカウントと投稿2件の再準備を依頼してください。

### 結果を確認できないとき

次のどちらかが表示された場合は、成功とも未変更とも決めません。

- `変更結果を確認できませんでした。通信を確認して投稿一覧を更新してください。`
- `削除結果を確認できませんでした。投稿一覧を更新して状態を確認してください。`

「投稿一覧を更新」を押し、現在見える状態を確かめます。

一覧の更新にも失敗した場合は、通信を戻してからもう一度更新してください。確認できない状態のまま、別の削除操作を重ねないようにします。

本人の操作が`true`になると対象行は一覧から消えるため、現行画面から同じIDへ再送できません。同じIDへの再試行は、学習者操作の対象外です。

## 確認問題

1. AからBへ切り替えたとき、`key={userId}`で投稿画面を作り直す理由を説明してください。
2. RPCが`false`を返す場合と、応答を確認できない場合の違いを説明してください。
3. 本人の操作後に投稿が一覧から消えたという観察だけでは、データベース内部の更新内容を断定できない理由を説明してください。

## 制作者向け境界

**NON_FORMAL_D4_CHAPTER_BUILD_CANDIDATE**

この章は候補です。正式D4/G6の合格は未測定です。本文の15コードブロックと前章Appの2か所の変更を検査しますが、その復元だけでは章のみの独立学習成功になりません。

学習者には、この章までの教材、開始Authアプリ、通常アカウントと宣言された公開入力だけを渡します。完成アプリや設計書を裏で参照して不足を埋めた実行は独立実走へ数えません。資格情報と実機接続は制作側が管理し、章やモデルworkspaceへ含めません。
