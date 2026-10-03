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
