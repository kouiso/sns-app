import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, StyleSheet, Text, TextInput, View } from 'react-native';
import type { SupabaseClient } from '@supabase/supabase-js';

import {
  createExclusiveOperation,
  createLatestRequestGuard,
  createProfileRepository,
} from '../lib/profile-flow.mjs';

type Route = 'profile-setup' | 'profile' | 'profile-edit' | 'timeline-placeholder';
type Profile = { id: string; username: string | null; displayName: string; bio: string | null };
type LoadState =
  | { kind: 'loading' }
  | { kind: 'empty' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; profile: Profile };

type Props = {
  client: SupabaseClient;
  userId: string;
  authMessage: string | null;
  authBusy: boolean;
  onSignOut: () => void;
};

export function ProfileShell({ client, userId, authMessage, authBusy, onSignOut }: Props) {
  const repository = useMemo(() => createProfileRepository(client), [client]);
  const guard = useMemo(() => createLatestRequestGuard(userId), [userId]);
  const saveLock = useRef(createExclusiveOperation());
  const [route, setRoute] = useState<Route>('profile-setup');
  const [loadState, setLoadState] = useState<LoadState>({ kind: 'loading' });
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const applyProfile = useCallback((profile: Profile) => {
    setUsername(profile.username ?? '');
    setDisplayName(profile.displayName);
    setBio(profile.bio ?? '');
    setLoadState({ kind: 'ready', profile });
    setRoute(profile.username ? 'profile' : 'profile-setup');
  }, []);

  const load = useCallback(async (showNotice = false) => {
    const request = guard.begin();
    setSaveMessage(null);
    setLoadState({ kind: 'loading' });
    const result = await repository.read(userId);
    if (!guard.accepts(request)) return;
    if (result.status === 'loaded' && result.profile) {
      applyProfile(result.profile);
      if (showNotice && result.profile.username) {
        setSaveMessage('現在のプロフィールを表示しています。');
      }
      return;
    }
    if (result.status === 'empty') {
      setLoadState({ kind: 'empty' });
      setRoute('profile-setup');
      return;
    }
    setLoadState({ kind: 'error', message: 'プロフィールを読み込めませんでした。' });
  }, [applyProfile, guard, repository, userId]);

  useEffect(() => {
    guard.switchUser(userId);
    void load();
    return () => guard.dispose();
  }, [guard, load, userId]);

  const save = useCallback(async () => {
    if (!saveLock.current.begin()) return;
    const request = guard.begin();
    setSaving(true);
    setSaveMessage(null);
    try {
      const result = await repository.save(userId, { username, displayName, bio });
      if (!guard.accepts(request)) return;
      if (result.status === 'saved' && result.profile) {
        applyProfile(result.profile);
        setSaveMessage('プロフィールを保存しました。');
      } else if (result.status === 'invalid') {
        setSaveMessage(result.message ?? '入力内容を確認してください。');
      } else if (result.status === 'conflict') {
        setSaveMessage('この表示IDは使われています。別の表示IDを入力してください。');
      } else if (result.status === 'zero_rows') {
        setSaveMessage('プロフィールを更新できませんでした。読み直して対象を確認してください。');
      } else if (result.status === 'unconfirmed') {
        setSaveMessage('保存結果を確認できませんでした。読み直して内容を確認してください。');
      } else {
        setSaveMessage('プロフィールを保存できませんでした。');
      }
    } finally {
      saveLock.current.finish();
      if (guard.accepts(request)) setSaving(false);
    }
  }, [applyProfile, bio, displayName, guard, repository, userId, username]);

  if (loadState.kind === 'loading') {
    return <Text testID="profile-loading">プロフィールを読み込んでいます</Text>;
  }

  if (loadState.kind === 'error') {
    return (
      <View testID="profile-load-error">
        <Text style={styles.message}>{loadState.message}</Text>
        <Button title="もう一度読み込む" onPress={() => void load(true)} disabled={authBusy} />
        <Button title="ログアウト" onPress={onSignOut} disabled={authBusy} testID="signout-button" />
      </View>
    );
  }

  if (loadState.kind === 'empty') {
    return (
      <View testID="profile-unavailable">
        <Text style={styles.message}>プロフィールの準備ができていません。読み直しても変わらない場合は、準備担当に確認してください。</Text>
        <Button title="もう一度読み込む" onPress={() => void load(true)} disabled={authBusy} />
        <Button title="ログアウト" onPress={onSignOut} disabled={authBusy} testID="signout-button" />
      </View>
    );
  }

  const editing = route === 'profile-setup' || route === 'profile-edit';
  if (editing) {
    return (
      <View testID={route === 'profile-edit' ? 'profile-edit-screen' : 'profile-setup-screen'}>
        <Text style={styles.heading}>{route === 'profile-edit' ? 'プロフィール編集' : 'プロフィール初期設定'}</Text>
        <Text style={styles.label}>表示ID</Text>
        <TextInput accessibilityLabel="表示ID" value={username} onChangeText={setUsername} placeholder="表示ID" maxLength={30} editable={!saving && !authBusy} style={styles.input} testID="profile-username-input" />
        <Text style={styles.label}>表示名</Text>
        <TextInput accessibilityLabel="表示名" value={displayName} onChangeText={setDisplayName} placeholder="表示名" maxLength={50} editable={!saving && !authBusy} style={styles.input} testID="profile-display-name-input" />
        <Text style={styles.label}>自己紹介（任意）</Text>
        <TextInput accessibilityLabel="自己紹介（任意）" value={bio} onChangeText={setBio} placeholder="自己紹介（任意）" maxLength={160} editable={!saving && !authBusy} multiline style={styles.input} testID="profile-bio-input" />
        <Button title={saving ? '保存しています' : '保存'} onPress={() => void save()} disabled={saving || authBusy} testID="profile-save-button" />
        <Text style={styles.message}>読み直すと、入力を保存せず現在のプロフィールに戻ります。</Text>
        <Button title="読み直す" onPress={() => void load(true)} disabled={saving || authBusy} testID="profile-reread-button" />
        {route === 'profile-edit' ? <Button title="入力を保存せず戻る" onPress={() => void load(true)} disabled={saving || authBusy} /> : null}
        {saveMessage ? <Text style={styles.message} testID="profile-save-message">{saveMessage}</Text> : null}
        {authMessage ? <Text style={styles.message}>{authMessage}</Text> : null}
        <Button title="ログアウト" onPress={onSignOut} disabled={saving || authBusy} testID="signout-button" />
      </View>
    );
  }

  if (route === 'timeline-placeholder') {
    return (
      <View testID="timeline-placeholder-screen">
        <Text style={styles.heading}>タイムライン</Text>
        <Text>タイムラインは準備中です。</Text>
        <Button title="プロフィールへ戻る" onPress={() => setRoute('profile')} />
      </View>
    );
  }

  const profile = loadState.kind === 'ready' ? loadState.profile : null;
  return (
    <View testID="profile-screen">
      <Text style={styles.heading}>{profile?.displayName || 'プロフィール'}</Text>
      <Text>@{profile?.username}</Text>
      <Text>{profile?.bio || '自己紹介はまだありません。'}</Text>
      <Button title="編集" onPress={() => setRoute('profile-edit')} testID="profile-edit-button" />
      <Button title="タイムラインへ" onPress={() => setRoute('timeline-placeholder')} testID="timeline-route-button" />
      <Button title="読み直す" onPress={() => void load(true)} disabled={authBusy} />
      {saveMessage ? <Text style={styles.message}>{saveMessage}</Text> : null}
      {authMessage ? <Text style={styles.message}>{authMessage}</Text> : null}
      <Button title="ログアウト" onPress={onSignOut} disabled={authBusy} testID="signout-button" />
    </View>
  );
}

const styles = StyleSheet.create({
  label: { fontSize: 16, fontWeight: '600', marginBottom: 6 },
  heading: { fontSize: 22, fontWeight: '700', marginBottom: 16 },
  input: { borderColor: '#94a3b8', borderWidth: 1, borderRadius: 8, padding: 12, marginBottom: 12 },
  message: { marginVertical: 12, color: '#334155' },
});
