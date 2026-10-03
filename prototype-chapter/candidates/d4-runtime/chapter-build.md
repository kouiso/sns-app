# 投稿画面を前章のアプリへ組み込む

**NON_FORMAL_D4_CHAPTER_BUILD_CANDIDATE**

磯貝）この章の開始アプリには、前章の認証アプリがあります。まだ投稿一覧や論理削除のボタンはありません。

阿部）この章のコードを足して、投稿を確かめる画面を作るんですね。

磯貝）はい。制作側が用意した通常アカウントA/Bと投稿2件を使います。管理キー、Docker、DB passwordは使いません。

## 開始状態を確認する

この章までの教材と、開始フォルダにあるAuthアプリを使います。教材外のアプリソースや設計書で不足を埋めないでください。

依存は前章と同じ固定ファイルです。公開接続情報と投稿2件のIDは、宣言された入力経路から制作側が渡します。

実機用Metro、Expoログインと接続経路は制作側が準備します。接続情報の欠落をURLやキーの推測で補いません。

阿部）開始時に投稿が見えていたら、そのまま進めますか。

磯貝）開始状態が違うので止めます。最初はサインイン後に「SNS のプロフィール機能は次の実装範囲です」と表示され、投稿画面は存在しないことを確認します。

## 投稿画面のファイルを作る

開始フォルダをエディターで開き、直下に`components`フォルダを作ります。その中へ`RlsTrial.tsx`を作ってください。

次のコードは、順番に連結して1つのファイルへ保存します。各ブロックの見出しはファイルへ入れません。

磯貝）短いブロックに分けていますが、別々のプログラムではありません。最初から最後まで続けて保存してください。

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

## サインイン後の画面につなぐ

`App.tsx`の先頭へ次のimportを追加してください。

```tsx
import { RlsTrial } from './components/RlsTrial';
```

サインイン後に表示する次の1行を探してください。パスワード変更の画面は引き続き使うので、変更不要です。

```tsx
<Text style={styles.body}>メール確認済みのセッションです。SNS のプロフィール機能は次の実装範囲です。</Text>
```

この1行だけを、次のコードへ置き換えてください。

```tsx
userId
  ? <RlsTrial key={userId} client={client} userId={userId} />
  : <Text style={styles.body}>ログイン状態をもう一度確認してください。</Text>
```

阿部）`key`に利用者IDを渡すのは、なぜですか。

磯貝）AからBへ切り替えたとき、前の利用者の画面状態を持ち越さないためです。サインインの処理そのものは前章のコードを使います。

## 型の検査と最初の画面

開始フォルダのターミナルで型を確認してください。依存の追加や固定ファイルの変更はありません。

```bash
npm run typecheck
```

制作側が用意した実機経路でアプリを開き、通常アカウントAでサインインしてください。今回の投稿2件と、自分・他の人の区別が見えることを確認するのが最初の課題です。

続いてBへ切り替え、Aの投稿の論理削除を試してください。変更しなかった文言と、制作担当のDB照合結果は別々の証拠として記録します。

通信が途切れた場合は成功や未変更と決めつけず、一覧を更新して状態を確認してください。必要な確認結果がそろわない試行も、失敗として残す対象です。

## 演習

1. AからBへ切り替えるとき、前の利用者の投稿画面を作り直す理由を説明してください。
2. RPCの応答が来ない場合に、DBが更新されていないと断定できない理由を説明してください。
3. 表示される2件と、他の試行で作られた投稿が混ざらない条件を確認してください。

## 制作メモ

この章は、前章のAuth19ソースから投稿画面を組み立てる手順候補です。独立モデルの章のみ実走、実機最初の画面、正式D4/G6の合格は未測定です。

本文に載せた15ブロックは投稿画面の全ソースです。制作側の検査はその連結と、前章Appの2か所の変更だけで型検査できることを確かめます。完成アプリを裏で参照して学習者の不足を埋める操作は、独立実走へ数えません。

開始manifestは前章19ファイルのhash集合を固定します。制作側の公開入力検査と実行全体leaseは別部品で、これらのunit成功を章だけの独立学習成功へ転用しません。
