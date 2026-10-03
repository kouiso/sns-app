import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AppState,
  Button,
  Linking,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import type { Session, SupabaseClient } from '@supabase/supabase-js';

import { createAuthReturnProcessor } from './lib/auth-return.mjs';
import { supabaseConfiguration } from './lib/supabase';

type SignedOutScreen = 'login' | 'signup' | 'confirmation' | 'reset-request';
type SessionState = 'loading' | 'signed_out' | 'signed_in';
type AuthMutation = Readonly<{ token: symbol; kind: 'action' | 'return' }>;

function isAuthReturnTarget(url: string, authReturnBase: string): boolean {
  try {
    const candidate = new URL(url);
    const configured = new URL(authReturnBase);
    return (
      candidate.protocol === configured.protocol &&
      candidate.hostname === configured.hostname &&
      candidate.port === configured.port &&
      candidate.pathname === configured.pathname
    );
  } catch {
    return false;
  }
}

function ConfigurationError({ message }: { message: string }) {
  return (
    <SafeAreaView style={styles.centered} testID="configuration-error">
      <Text style={styles.title}>接続設定が必要です</Text>
      <Text style={styles.message}>{message}</Text>
      <Text style={styles.help}>設定後に Expo を再起動してください。</Text>
      <StatusBar style="dark" />
    </SafeAreaView>
  );
}

function AuthApp({ client, authReturnBase }: { client: SupabaseClient; authReturnBase: string }) {
  const processor = useMemo(
    () => createAuthReturnProcessor({ auth: client.auth, returnBase: authReturnBase }),
    [authReturnBase, client],
  );
  const [sessionState, setSessionState] = useState<SessionState>('loading');
  const [userId, setUserId] = useState<string | null>(null);
  const [screen, setScreen] = useState<SignedOutScreen>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [recoveryUserId, setRecoveryUserId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [resendSeconds, setResendSeconds] = useState(0);
  const reconciliationGeneration = useRef(0);
  const securityEpoch = useRef(0);
  const authMutation = useRef<AuthMutation | null>(null);
  const suppressedAuthEvent = useRef(false);

  const beginAuthMutation = useCallback((kind: AuthMutation['kind']) => {
    if (authMutation.current) return null;
    const mutation = Object.freeze({ token: Symbol(kind), kind });
    authMutation.current = mutation;
    setBusy(true);
    return mutation;
  }, []);

  const finishAuthMutation = useCallback((mutation: AuthMutation) => {
    if (authMutation.current?.token !== mutation.token) return;
    authMutation.current = null;
    setBusy(false);
  }, []);

  const showSignedOut = useCallback(() => {
    securityEpoch.current += 1;
    reconciliationGeneration.current += 1;
    setUserId(null);
    setRecoveryUserId(null);
    setSessionState('signed_out');
  }, []);

  const reconcileSession = useCallback(
    async (
      session: Session | null,
      keepLoadingOnFailure = false,
      expectedSecurityEpoch?: number,
    ) => {
      const startedAtEpoch = expectedSecurityEpoch ?? securityEpoch.current;
      const generation = ++reconciliationGeneration.current;
      if (!session) {
        if (startedAtEpoch !== securityEpoch.current) return;
        showSignedOut();
        return;
      }
      let response;
      try {
        response = await client.auth.getUser();
      } catch {
        if (
          generation !== reconciliationGeneration.current ||
          startedAtEpoch !== securityEpoch.current
        ) return;
        setRecoveryUserId(null);
        setMessage('ログイン状態を確認できませんでした。通信を確認してもう一度お試しください。');
        setSessionState(keepLoadingOnFailure ? 'loading' : 'signed_out');
        setUserId(null);
        return;
      }
      if (generation !== reconciliationGeneration.current) return;
      if (startedAtEpoch !== securityEpoch.current) return;
      const { data, error } = response;
      if (error || !data.user || data.user.id !== session.user.id) {
        setRecoveryUserId(null);
        setMessage('ログイン状態を確認できませんでした。通信を確認してもう一度お試しください。');
        setSessionState(keepLoadingOnFailure ? 'loading' : 'signed_out');
        setUserId(null);
        return;
      }
      if (!data.user.email_confirmed_at) {
        showSignedOut();
        setScreen('confirmation');
        return;
      }
      setRecoveryUserId((current) => (current === data.user.id ? current : null));
      setUserId(data.user.id);
      setSessionState('signed_in');
    },
    [client, showSignedOut],
  );

  const restoreSession = useCallback(async () => {
    const startedAtEpoch = securityEpoch.current;
    const generation = ++reconciliationGeneration.current;
    setSessionState('loading');
    setMessage(null);
    try {
      const { data, error } = await client.auth.getSession();
      if (
        startedAtEpoch !== securityEpoch.current ||
        generation !== reconciliationGeneration.current
      ) return;
      if (error) {
        setMessage('保存されたログイン状態を読み込めませんでした。');
        return;
      }
      await reconcileSession(data.session, true, startedAtEpoch);
    } catch {
      if (
        startedAtEpoch !== securityEpoch.current ||
        generation !== reconciliationGeneration.current
      ) return;
      setMessage('保存されたログイン状態を読み込めませんでした。');
    }
  }, [client, reconcileSession]);

  const handleAuthReturn = useCallback(
    async (url: string) => {
      const mutation = beginAuthMutation('return');
      if (!mutation) {
        setMessage('別の認証処理を確認しています。完了後にもう一度お試しください。');
        return;
      }
      securityEpoch.current += 1;
      reconciliationGeneration.current += 1;
      const startedAtEpoch = securityEpoch.current;
      suppressedAuthEvent.current = false;
      setMessage(null);
      try {
        const result = await processor.process(url);
        if (startedAtEpoch !== securityEpoch.current) return;
        if (result.status === 'approved') {
          setUserId(result.userId);
          setSessionState('signed_in');
          setMessage(
            result.purpose === 'recovery'
              ? '本人確認が完了しました。新しいパスワードを設定してください。'
              : 'メールアドレスを確認しました。',
          );
          setRecoveryUserId(result.purpose === 'recovery' ? result.userId : null);
          return;
        }
        if (result.status === 'reconciliation_needed') {
          setRecoveryUserId(null);
          setMessage('リンクの確認後にログイン状態を検証できませんでした。このリンクは再利用せず、新しい確認メールまたは再設定メールを送信してください。');
          const { data } = await client.auth.getSession();
          if (startedAtEpoch !== securityEpoch.current) return;
          await reconcileSession(data.session, true, startedAtEpoch);
          return;
        }
        if (result.status === 'already_processed') {
          setMessage('このリンクはすでに処理されています。新しいメールから開いてください。');
          return;
        }
        setMessage('認証リンクを確認できませんでした。新しいメールからもう一度お試しください。');
      } catch {
        if (startedAtEpoch !== securityEpoch.current) return;
        setRecoveryUserId(null);
        setSessionState('loading');
        setMessage('認証状態を確認できませんでした。新しいメールを送信してもう一度お試しください。');
      } finally {
        if (
          suppressedAuthEvent.current &&
          startedAtEpoch === securityEpoch.current
        ) {
          suppressedAuthEvent.current = false;
          try {
            const { data, error } = await client.auth.getSession();
            if (startedAtEpoch === securityEpoch.current) {
              if (error) {
                setRecoveryUserId(null);
                setSessionState('loading');
                setMessage('認証状態を確認できませんでした。通信を確認してもう一度お試しください。');
              } else {
                await reconcileSession(data.session, true, startedAtEpoch);
              }
            }
          } catch {
            if (startedAtEpoch === securityEpoch.current) {
              setRecoveryUserId(null);
              setSessionState('loading');
              setMessage('認証状態を確認できませんでした。通信を確認してもう一度お試しください。');
            }
          }
        }
        suppressedAuthEvent.current = false;
        finishAuthMutation(mutation);
      }
    },
    [beginAuthMutation, client, finishAuthMutation, processor, reconcileSession],
  );

  useEffect(() => {
    const deferredAuthTasks = new Set<ReturnType<typeof setTimeout>>();
    const { data } = client.auth.onAuthStateChange((_event, session) => {
      if (authMutation.current?.kind === 'return') {
        suppressedAuthEvent.current = true;
        return;
      }
      if (!session) {
        showSignedOut();
        return;
      }
      const scheduledAtEpoch = securityEpoch.current;
      const task = setTimeout(() => {
        deferredAuthTasks.delete(task);
        if (authMutation.current?.kind === 'return') {
          suppressedAuthEvent.current = true;
          return;
        }
        if (scheduledAtEpoch !== securityEpoch.current) return;
        void reconcileSession(session, false, scheduledAtEpoch);
      }, 0);
      deferredAuthTasks.add(task);
    });
    const linkingSubscription = Linking.addEventListener('url', ({ url }) => {
      if (isAuthReturnTarget(url, authReturnBase)) void handleAuthReturn(url);
    });
    void Linking.getInitialURL()
      .then((url) => {
        if (url && isAuthReturnTarget(url, authReturnBase)) void handleAuthReturn(url);
      })
      .catch(() => setMessage('起動時の認証リンクを読み込めませんでした。'));
    void restoreSession();
    return () => {
      for (const task of deferredAuthTasks) clearTimeout(task);
      data.subscription.unsubscribe();
      linkingSubscription.remove();
    };
  }, [authReturnBase, client, handleAuthReturn, reconcileSession, restoreSession, showSignedOut]);

  useEffect(() => {
    const applyState = (state: string) => {
      if (state === 'active') void client.auth.startAutoRefresh();
      else void client.auth.stopAutoRefresh();
    };
    applyState(AppState.currentState);
    const subscription = AppState.addEventListener('change', applyState);
    return () => {
      subscription.remove();
      void client.auth.stopAutoRefresh();
    };
  }, [client]);

  useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = setInterval(() => {
      setResendSeconds((current) => Math.max(0, current - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendSeconds]);

  const run = async (operation: () => Promise<void>) => {
    const mutation = beginAuthMutation('action');
    if (!mutation) {
      setMessage('別の認証処理を確認しています。完了後にもう一度お試しください。');
      return;
    }
    setMessage(null);
    try {
      await operation();
    } catch {
      setRecoveryUserId(null);
      setMessage('通信に失敗しました。時間を空けてもう一度お試しください。');
    } finally {
      finishAuthMutation(mutation);
    }
  };

  const login = () => run(async () => {
    securityEpoch.current += 1;
    reconciliationGeneration.current += 1;
    if (!email.trim() || !password) {
      setMessage('メールアドレスとパスワードを入力してください。');
      return;
    }
    const { data, error } = await client.auth.signInWithPassword({ email: email.trim(), password });
    if (error || !data.session) {
      setMessage('ログインできませんでした。入力内容を確認してください。');
      return;
    }
    await reconcileSession(data.session);
  });

  const signup = () => run(async () => {
    securityEpoch.current += 1;
    reconciliationGeneration.current += 1;
    if (!email.trim() || !password) {
      setMessage('メールアドレスとパスワードを入力してください。');
      return;
    }
    const { data, error } = await client.auth.signUp({
      email: email.trim(),
      password,
      options: { emailRedirectTo: authReturnBase },
    });
    if (error) {
      setMessage('登録を開始できませんでした。入力内容を確認して時間を空けてお試しください。');
      return;
    }
    if (data.session) {
      await reconcileSession(data.session);
      return;
    }
    setScreen('confirmation');
    setResendSeconds(60);
    setMessage('確認メールを送信しました。');
  });

  const resendConfirmation = () => run(async () => {
    if (resendSeconds > 0 || !email.trim()) return;
    const { error } = await client.auth.resend({
      type: 'signup',
      email: email.trim(),
      options: { emailRedirectTo: authReturnBase },
    });
    if (error) {
      setMessage('確認メールを再送できませんでした。時間を空けてお試しください。');
      return;
    }
    setResendSeconds(60);
    setMessage('確認メールを再送しました。');
  });

  const requestReset = () => run(async () => {
    if (!email.trim()) {
      setMessage('メールアドレスを入力してください。');
      return;
    }
    const { error } = await client.auth.resetPasswordForEmail(email.trim(), { redirectTo: authReturnBase });
    setMessage(error
      ? '再設定メールを送信できませんでした。時間を空けてお試しください。'
      : '再設定メールを送信しました。メール内のリンクをこの端末で開いてください。');
  });

  const saveNewPassword = () => run(async () => {
    if (!userId || recoveryUserId !== userId) {
      setMessage('再設定メールのリンクから本人確認をやり直してください。');
      setRecoveryUserId(null);
      return;
    }
    if (!newPassword) {
      setMessage('新しいパスワードを入力してください。');
      return;
    }
    const { error } = await client.auth.updateUser({ password: newPassword });
    if (error) {
      setMessage('パスワードを保存できませんでした。入力内容を確認してください。');
      return;
    }
    setNewPassword('');
    setRecoveryUserId(null);
    setMessage('パスワードを更新しました。');
  });

  const signOut = () => run(async () => {
    securityEpoch.current += 1;
    reconciliationGeneration.current += 1;
    setRecoveryUserId(null);
    const { error } = await client.auth.signOut();
    if (error) {
      setMessage('ログアウトできませんでした。通信を確認してください。');
      return;
    }
    showSignedOut();
    setScreen('login');
    setPassword('');
  });

  if (sessionState === 'loading') {
    return (
      <SafeAreaView style={styles.centered} testID="auth-loading">
        <Text style={styles.title}>ログイン状態を確認しています</Text>
        {message ? <Text style={styles.message}>{message}</Text> : null}
        {message ? <Button title="もう一度確認" onPress={() => void restoreSession()} disabled={busy} testID="retry-session-button" /> : null}
        <StatusBar style="dark" />
      </SafeAreaView>
    );
  }

  if (sessionState === 'signed_in') {
    return (
      <SafeAreaView style={styles.safe} testID={recoveryUserId ? 'password-reset-screen' : 'profile-screen'}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.title}>{recoveryUserId ? '新しいパスワード' : 'プロフィール準備中'}</Text>
          {recoveryUserId ? (
            <>
              <Text style={styles.body}>確認済みのアカウントに新しいパスワードを設定します。</Text>
              <TextInput
                value={newPassword}
                onChangeText={setNewPassword}
                placeholder="新しいパスワード"
                secureTextEntry
                autoCapitalize="none"
                editable={!busy}
                style={styles.input}
                testID="new-password-input"
              />
              <Button title="パスワードを保存" onPress={saveNewPassword} disabled={busy} testID="save-password-button" />
            </>
          ) : (
            <Text style={styles.body}>メール確認済みのセッションです。SNS のプロフィール機能は次の実装範囲です。</Text>
          )}
          {message ? <Text style={styles.message} testID="status-message">{message}</Text> : null}
          <View style={styles.spacer} />
          <Button title="ログアウト" onPress={signOut} disabled={busy} testID="signout-button" />
        </ScrollView>
        <StatusBar style="dark" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {screen === 'confirmation' ? (
          <View testID="confirmation-wait">
            <Text style={styles.title}>確認メールを開いてください</Text>
            <Text style={styles.body}>登録したメールアドレスへ確認メールを送りました。この端末でリンクを開いてください。</Text>
            <Button
              title={resendSeconds > 0 ? `再送まで ${resendSeconds} 秒` : '確認メールを再送'}
              onPress={resendConfirmation}
              disabled={busy || resendSeconds > 0}
              testID="resend-button"
            />
            <View style={styles.smallSpacer} />
            <Button
              title="メールアプリを開く"
              onPress={() => void Linking.openURL('mailto:').catch(() => setMessage('メールアプリを開けませんでした。'))}
              disabled={busy}
              testID="open-mail-button"
            />
            <View style={styles.smallSpacer} />
            <Button title="別のアドレスで登録し直す" onPress={() => { setScreen('signup'); setMessage(null); }} disabled={busy} testID="restart-signup-button" />
          </View>
        ) : (
          <>
            <Text style={styles.title}>
              {screen === 'login' ? 'ログイン' : screen === 'signup' ? '新規登録' : 'パスワードを再設定'}
            </Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="メールアドレス"
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              editable={!busy}
              style={styles.input}
              testID="email-input"
            />
            {screen !== 'reset-request' ? (
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="パスワード"
                secureTextEntry
                autoCapitalize="none"
                editable={!busy}
                style={styles.input}
                testID="password-input"
              />
            ) : null}
            <Button
              title={screen === 'login' ? 'ログイン' : screen === 'signup' ? '登録する' : '再設定メールを送る'}
              onPress={screen === 'login' ? login : screen === 'signup' ? signup : requestReset}
              disabled={busy}
              testID={screen === 'login' ? 'login-button' : screen === 'signup' ? 'signup-button' : 'reset-request-button'}
            />
            <View style={styles.spacer} />
            {screen === 'login' ? (
              <>
                <Button title="新規登録へ" onPress={() => setScreen('signup')} disabled={busy} testID="show-signup-button" />
                <View style={styles.smallSpacer} />
                <Button title="パスワードを忘れた" onPress={() => setScreen('reset-request')} disabled={busy} testID="show-reset-request-button" />
              </>
            ) : (
              <Button title="ログインへ戻る" onPress={() => setScreen('login')} disabled={busy} testID="show-login-button" />
            )}
          </>
        )}
        {message ? <Text style={styles.message} testID="status-message">{message}</Text> : null}
      </ScrollView>
      <StatusBar style="dark" />
    </SafeAreaView>
  );
}

export default function App() {
  if (!supabaseConfiguration.ok) return <ConfigurationError message={supabaseConfiguration.message} />;
  return <AuthApp client={supabaseConfiguration.client} authReturnBase={supabaseConfiguration.authReturnBase} />;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f7f8fa' },
  centered: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#f7f8fa', gap: 16 },
  content: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  title: { fontSize: 26, fontWeight: '700', color: '#172033', marginBottom: 20 },
  body: { fontSize: 16, lineHeight: 24, color: '#44506a', marginBottom: 20 },
  help: { fontSize: 14, lineHeight: 20, color: '#667085' },
  input: { backgroundColor: '#fff', borderColor: '#c8ceda', borderWidth: 1, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, marginBottom: 14 },
  message: { marginTop: 18, padding: 12, borderRadius: 8, backgroundColor: '#eef2ff', color: '#27345f', lineHeight: 21 },
  spacer: { height: 24 },
  smallSpacer: { height: 12 },
});
