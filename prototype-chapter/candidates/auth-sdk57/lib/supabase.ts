import 'react-native-url-polyfill/auto';

import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient, processLock, type SupabaseClient } from '@supabase/supabase-js';

type SupabaseConfiguration =
  | Readonly<{
      ok: true;
      authReturnBase: string;
      client: SupabaseClient;
    }>
  | Readonly<{
      ok: false;
      message: string;
    }>;

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL?.trim();
const publishableKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim();
const authReturnBase = process.env.EXPO_PUBLIC_AUTH_RETURN_BASE?.trim();
const trialLanHost = process.env.EXPO_PUBLIC_AUTH_TRIAL_LAN_HOST?.trim();

function decodeBase64UrlAscii(value: string): string | null {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  let bits = 0;
  let bitCount = 0;
  let output = '';

  for (const character of normalized) {
    if (character === '=') break;
    const digit = alphabet.indexOf(character);
    if (digit < 0) return null;
    bits = (bits << 6) | digit;
    bitCount += 6;
    if (bitCount >= 8) {
      bitCount -= 8;
      output += String.fromCharCode((bits >> bitCount) & 0xff);
      bits &= (1 << bitCount) - 1;
    }
  }
  return output;
}

function readLegacyRole(key: string): string | null {
  const parts = key.split('.');
  if (parts.length !== 3) return null;
  const payload = decodeBase64UrlAscii(parts[1]);
  if (!payload) return null;
  try {
    const parsed = JSON.parse(payload) as { role?: unknown };
    return typeof parsed.role === 'string' ? parsed.role : null;
  } catch {
    return null;
  }
}

function isLocalSupabaseUrl(value: URL): boolean {
  return (
    value.hostname === 'localhost' ||
    value.hostname === '127.0.0.1' ||
    value.hostname === '10.0.2.2' ||
    (Boolean(trialLanHost) && value.hostname === trialLanHost)
  );
}

function configurationError(): string | null {
  if (!supabaseUrl || !publishableKey || !authReturnBase) {
    return '環境変数 EXPO_PUBLIC_SUPABASE_URL、EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY、EXPO_PUBLIC_AUTH_RETURN_BASE を設定してください。';
  }

  let parsedUrl: URL;
  let parsedReturn: URL;
  try {
    parsedUrl = new URL(supabaseUrl);
    parsedReturn = new URL(authReturnBase);
  } catch {
    return 'Supabase URL または認証の戻り先 URL の形式を確認してください。';
  }

  if (!parsedUrl.hostname || (parsedUrl.protocol !== 'https:' && !isLocalSupabaseUrl(parsedUrl))) {
    return 'Supabase URL は HTTPS を使ってください。ローカル開発先だけ HTTP を利用できます。';
  }
  if (
    !parsedReturn.protocol ||
    !parsedReturn.hostname ||
    !parsedReturn.pathname ||
    parsedReturn.search ||
    parsedReturn.hash ||
    parsedReturn.username ||
    parsedReturn.password
  ) {
    return '認証の戻り先はクエリやフラグメントを含まない完全な URL にしてください。';
  }

  if (publishableKey.startsWith('sb_secret_')) {
    return 'クライアントには Supabase の publishable key を設定してください。secret key は使用できません。';
  }
  const legacyRole = readLegacyRole(publishableKey);
  if (legacyRole === 'service_role') {
    return 'クライアントには service_role key を設定できません。';
  }
  if (legacyRole && (legacyRole !== 'anon' || !isLocalSupabaseUrl(parsedUrl))) {
    return 'legacy anon key はローカル互換確認にだけ使用できます。publishable key を設定してください。';
  }
  if (!publishableKey.startsWith('sb_publishable_') && legacyRole !== 'anon') {
    return 'Supabase の publishable key を設定してください。';
  }
  return null;
}

const errorMessage = configurationError();

export const supabaseConfiguration: SupabaseConfiguration = errorMessage
  ? Object.freeze({ ok: false, message: errorMessage })
  : Object.freeze({
      ok: true,
      authReturnBase: authReturnBase!,
      client: createClient(supabaseUrl!, publishableKey!, {
        auth: {
          storage: AsyncStorage,
          autoRefreshToken: true,
          persistSession: true,
          detectSessionInUrl: false,
          lock: processLock,
        },
      }),
    });
