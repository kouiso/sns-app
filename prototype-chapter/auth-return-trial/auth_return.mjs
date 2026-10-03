import { createHash } from 'node:crypto';

const CONTROL_PARAMETERS = new Set([
  'access_token',
  'refresh_token',
  'type',
  'code',
  'error',
  'error_code',
  'error_description',
]);

const PROVIDER_ERROR_PARAMETERS = [
  'error',
  'error_code',
  'error_description',
];

const UNSAFE_SCHEMES = new Set(['data:', 'file:', 'javascript:', 'blob:']);

const failure = (code) => Object.freeze({ ok: false, code });

function hasInvalidPercentEncoding(text) {
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] !== '%') continue;
    if (!/^[0-9a-fA-F]{2}$/.test(text.slice(index + 1, index + 3))) return true;
    index += 2;
  }
  return false;
}

function readParameters(component) {
  if (hasInvalidPercentEncoding(component)) {
    return { error: failure('invalid_percent_encoding') };
  }

  const values = new Map();
  for (const [key, value] of new URLSearchParams(component)) {
    if (values.has(key)) return { error: failure('duplicate_parameter') };
    values.set(key, value);
  }
  return { values };
}

function hasControlParameter(values) {
  for (const key of values.keys()) {
    if (CONTROL_PARAMETERS.has(key)) return true;
  }
  return false;
}

function parseConfiguredRedirect(redirectTo) {
  if (typeof redirectTo !== 'string' || redirectTo.length === 0) {
    throw new TypeError('redirectTo must be a non-empty URL string');
  }

  let url;
  try {
    url = new URL(redirectTo);
  } catch {
    throw new TypeError('redirectTo must be an absolute URL');
  }

  if (url.search || url.hash || url.username || url.password) {
    throw new TypeError('redirectTo must contain only a scheme, host, port, and path');
  }
  if (UNSAFE_SCHEMES.has(url.protocol)) {
    throw new TypeError('redirectTo uses an unsafe scheme');
  }
  if (url.protocol === 'http:' && !['localhost', '127.0.0.1'].includes(url.hostname)) {
    throw new TypeError('cleartext redirectTo is allowed only for local loopback trials');
  }

  return Object.freeze({
    protocol: url.protocol,
    host: url.host,
    pathname: url.pathname,
  });
}

function matchesRedirect(url, configured) {
  return (
    url.protocol === configured.protocol &&
    url.host === configured.host &&
    url.pathname === configured.pathname &&
    url.username === '' &&
    url.password === ''
  );
}

function fingerprint(rawURL) {
  return createHash('sha256').update(rawURL, 'utf8').digest('hex');
}

function isStrictRawURL(rawURL) {
  return (
    typeof rawURL === 'string' &&
    rawURL.length > 0 &&
    rawURL.length <= 16_384 &&
    !/[\u0000-\u0020\u007f]/.test(rawURL)
  );
}

function parseReturn(rawURL, configuredRedirect) {
  let url;
  try {
    url = new URL(rawURL);
  } catch {
    return { error: failure('invalid_url') };
  }

  if (!matchesRedirect(url, configuredRedirect)) {
    return { error: failure('redirect_mismatch') };
  }

  const query = readParameters(url.search.slice(1));
  if (query.error) return query;
  const fragment = readParameters(url.hash.slice(1));
  if (fragment.error) return fragment;

  if (hasControlParameter(query.values) && hasControlParameter(fragment.values)) {
    return { error: failure('ambiguous_parameter_location') };
  }

  const parameters = hasControlParameter(fragment.values) ? fragment.values : query.values;

  if (PROVIDER_ERROR_PARAMETERS.some((key) => parameters.has(key))) {
    return { error: failure('provider_error') };
  }
  if (parameters.has('code')) return { error: failure('unsupported_pkce_flow') };

  const type = parameters.get('type');
  if (!['signup', 'recovery'].includes(type)) {
    return { error: failure('unsupported_type') };
  }

  const accessToken = parameters.get('access_token');
  const refreshToken = parameters.get('refresh_token');
  if (!accessToken || !refreshToken) return { error: failure('missing_tokens') };

  return { type, accessToken, refreshToken };
}

function userId(value) {
  return typeof value === 'string' && value.length > 0 ? value : null;
}

/**
 * Creates a deliberately narrow implicit-token auth-return receiver trial.
 * The injected auth object must expose async setSession() and getUser().
 */
export function createAuthReturnHandler({
  redirectTo,
  auth,
  verifyRecoveryPurpose,
  completedCacheSize = 32,
}) {
  const configuredRedirect = parseConfiguredRedirect(redirectTo);
  if (!auth || typeof auth.setSession !== 'function' || typeof auth.getUser !== 'function') {
    throw new TypeError('auth must expose setSession and getUser functions');
  }
  if (verifyRecoveryPurpose !== undefined && typeof verifyRecoveryPurpose !== 'function') {
    throw new TypeError('verifyRecoveryPurpose must be a function when supplied');
  }
  if (!Number.isInteger(completedCacheSize) || completedCacheSize < 1 || completedCacheSize > 256) {
    throw new TypeError('completedCacheSize must be an integer from 1 through 256');
  }

  const completed = new Map();
  let active = null;

  async function processReturn(rawURL) {
    const parsed = parseReturn(rawURL, configuredRedirect);
    if (parsed.error) return parsed.error;

    if (parsed.type === 'recovery') {
      if (!verifyRecoveryPurpose) return failure('recovery_purpose_unverified');
      let purposeVerified = false;
      try {
        purposeVerified =
          (await verifyRecoveryPurpose({
            accessToken: parsed.accessToken,
            refreshToken: parsed.refreshToken,
          })) === true;
      } catch {
        purposeVerified = false;
      }
      if (!purposeVerified) return failure('recovery_purpose_unverified');
    }

    let sessionResult;
    try {
      sessionResult = await auth.setSession({
        access_token: parsed.accessToken,
        refresh_token: parsed.refreshToken,
      });
    } catch {
      return failure('set_session_failed');
    }
    if (sessionResult?.error) return failure('set_session_failed');

    const session = sessionResult?.data?.session;
    if (!session) return failure('missing_session');

    let userResult;
    try {
      userResult = await auth.getUser();
    } catch {
      return failure('get_user_failed');
    }
    if (userResult?.error) return failure('get_user_failed');

    const user = userResult?.data?.user;
    if (!user) return failure('missing_user');

    const sessionUserId = userId(session?.user?.id);
    const authoritativeUserId = userId(user.id);
    if (!sessionUserId || !authoritativeUserId || sessionUserId !== authoritativeUserId) {
      return failure('user_identity_mismatch');
    }

    if (
      parsed.type === 'signup' &&
      (typeof user.email_confirmed_at !== 'string' || user.email_confirmed_at.length === 0)
    ) {
      return failure('email_not_confirmed');
    }

    if (parsed.type === 'signup') {
      return Object.freeze({
        ok: true,
        flow: 'signup',
        route: 'profile-setup',
        assurance: 'confirmed-session',
      });
    }

    return Object.freeze({
      ok: true,
      flow: 'recovery',
      route: 'password-reset',
      assurance: 'trusted-purpose-and-verified-session',
    });
  }

  function remember(digest) {
    completed.set(digest, true);
    while (completed.size > completedCacheSize) {
      completed.delete(completed.keys().next().value);
    }
  }

  return function handleAuthReturn(rawURL) {
    if (!isStrictRawURL(rawURL)) return Promise.resolve(failure('invalid_url'));
    const digest = fingerprint(rawURL);

    if (active) {
      if (digest === active.digest) return active.promise;
      return Promise.resolve(failure('concurrent_link_conflict'));
    }

    if (completed.has(digest)) {
      return Promise.resolve(failure('already_processed'));
    }

    const promise = processReturn(rawURL).then(
      (result) => {
        if (result.ok) remember(digest);
        return result;
      },
      () => failure('auth_return_failed'),
    );
    active = { digest, promise };
    promise.finally(() => {
      if (active?.promise === promise) active = null;
    });
    return promise;
  };
}
