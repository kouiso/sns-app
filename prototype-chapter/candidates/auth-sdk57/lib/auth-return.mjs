const ALLOWED_TYPES = new Set(['signup', 'recovery']);
const ALLOWED_QUERY_KEYS = new Set(['token_hash', 'type']);
const DEFAULT_CACHE_SIZE = 32;
const MAX_URL_LENGTH = 4096;

export class AuthReturnError extends Error {
  constructor(code) {
    super(code);
    this.name = 'AuthReturnError';
    this.code = code;
  }
}

function fail(code) {
  throw new AuthReturnError(code);
}

function hasControlCharacter(value) {
  return /[\u0000-\u001f\u007f]/.test(value);
}

function assertWellFormedPercentEncoding(value) {
  if (/%(?![0-9a-fA-F]{2})/.test(value)) {
    fail('malformed_percent_encoding');
  }
}

function parseConfiguredBase(returnBase) {
  if (typeof returnBase !== 'string' || returnBase.length === 0 || returnBase.length > MAX_URL_LENGTH) {
    fail('invalid_configuration');
  }
  if (hasControlCharacter(returnBase) || returnBase.includes('#')) {
    fail('invalid_configuration');
  }
  assertWellFormedPercentEncoding(returnBase);

  let base;
  try {
    base = new URL(returnBase);
  } catch {
    fail('invalid_configuration');
  }

  if (
    base.username ||
    base.password ||
    base.search ||
    base.hash ||
    !base.protocol ||
    !base.hostname ||
    !base.pathname
  ) {
    fail('invalid_configuration');
  }
  return base;
}

export function parseAuthReturnUrl(rawUrl, returnBase) {
  const base = parseConfiguredBase(returnBase);
  if (typeof rawUrl !== 'string' || rawUrl.length === 0 || rawUrl.length > MAX_URL_LENGTH) {
    fail('invalid_url');
  }
  if (hasControlCharacter(rawUrl)) {
    fail('control_character');
  }
  if (rawUrl.includes('#')) {
    fail('fragment_not_allowed');
  }
  assertWellFormedPercentEncoding(rawUrl);

  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    fail('invalid_url');
  }

  if (
    parsed.protocol !== base.protocol ||
    parsed.hostname !== base.hostname ||
    parsed.port !== base.port ||
    parsed.pathname !== base.pathname ||
    parsed.username ||
    parsed.password
  ) {
    fail('return_target_mismatch');
  }

  const values = new Map();
  for (const [key, value] of parsed.searchParams) {
    if (!ALLOWED_QUERY_KEYS.has(key)) {
      fail('unexpected_query_parameter');
    }
    if (values.has(key)) {
      fail('duplicate_query_parameter');
    }
    values.set(key, value);
  }

  if (values.size !== 2 || !values.has('token_hash') || !values.has('type')) {
    fail('missing_query_parameter');
  }

  const tokenHash = values.get('token_hash');
  const type = values.get('type');
  if (
    typeof tokenHash !== 'string' ||
    tokenHash.length === 0 ||
    tokenHash.length > 2048 ||
    hasControlCharacter(tokenHash) ||
    /\s/.test(tokenHash)
  ) {
    fail('invalid_token_hash');
  }
  if (!ALLOWED_TYPES.has(type)) {
    fail('unsupported_type');
  }

  return Object.freeze({ tokenHash, type });
}

function isConfirmedUser(user) {
  return Boolean(
    user &&
    typeof user.email_confirmed_at === 'string' &&
    user.email_confirmed_at.length > 0
  );
}

function publicFailure(code, sessionMutated = false, reconciliationNeeded = false) {
  return Object.freeze({
    status: reconciliationNeeded ? 'reconciliation_needed' : 'rejected',
    code,
    sessionMutated,
    reconciliationNeeded,
  });
}

export function createAuthReturnProcessor({ auth, returnBase, maxCompleted = DEFAULT_CACHE_SIZE }) {
  parseConfiguredBase(returnBase);
  if (!auth || typeof auth.verifyOtp !== 'function' || typeof auth.getUser !== 'function') {
    fail('invalid_configuration');
  }
  if (!Number.isInteger(maxCompleted) || maxCompleted < 1 || maxCompleted > 256) {
    fail('invalid_configuration');
  }

  const completed = new Map();
  const completedOrder = [];
  const inFlight = new Map();

  function rememberBounded(map, order, key, value) {
    if (!map.has(key)) {
      order.push(key);
    }
    map.set(key, value);
    while (order.length > maxCompleted) {
      const oldest = order.shift();
      map.delete(oldest);
    }
  }

  function markCompleted(rawUrl) {
    rememberBounded(completed, completedOrder, rawUrl, true);
  }

  async function validateAuthoritativeUser(rawUrl, expected) {
    let response;
    try {
      response = await auth.getUser();
    } catch {
      return publicFailure('authoritative_user_unavailable', expected.sessionMutated, true);
    }

    const user = response?.data?.user;
    if (response?.error || !user) {
      return publicFailure('authoritative_user_unavailable', expected.sessionMutated, true);
    }
    if (user.id !== expected.userId) {
      return publicFailure('authoritative_user_mismatch', expected.sessionMutated, true);
    }
    if (!isConfirmedUser(user)) {
      return publicFailure('user_not_confirmed', expected.sessionMutated, true);
    }

    markCompleted(rawUrl);
    return Object.freeze({
      status: 'approved',
      purpose: expected.type,
      userId: user.id,
      sessionMutated: expected.sessionMutated,
      reconciliationNeeded: false,
    });
  }

  async function run(rawUrl) {
    let parsed;
    try {
      parsed = parseAuthReturnUrl(rawUrl, returnBase);
    } catch (error) {
      if (error instanceof AuthReturnError) {
        return publicFailure(error.code);
      }
      return publicFailure('invalid_url');
    }

    if (completed.has(rawUrl)) {
      return Object.freeze({
        status: 'already_processed',
        code: 'already_processed',
        sessionMutated: false,
        reconciliationNeeded: false,
      });
    }

    let verification;
    try {
      verification = await auth.verifyOtp({ token_hash: parsed.tokenHash, type: parsed.type });
    } catch {
      return publicFailure('verification_unavailable', true, true);
    }

    const sessionMutated = Boolean(verification?.data?.session);
    if (verification?.error) {
      return publicFailure(
        'verification_failed',
        sessionMutated,
        sessionMutated,
      );
    }

    const verifiedUser = verification?.data?.user;
    if (!verifiedUser?.id) {
      return publicFailure('verification_incomplete', sessionMutated, sessionMutated);
    }
    if (!sessionMutated) {
      return publicFailure('verification_incomplete', false, true);
    }

    const expected = Object.freeze({
      type: parsed.type,
      userId: verifiedUser.id,
      sessionMutated,
    });
    return validateAuthoritativeUser(rawUrl, expected);
  }

  return Object.freeze({
    process(rawUrl) {
      if (typeof rawUrl !== 'string') {
        return Promise.resolve(publicFailure('invalid_url'));
      }
      const existing = inFlight.get(rawUrl);
      if (existing) {
        return existing;
      }
      if (inFlight.size > 0) {
        return Promise.resolve(publicFailure('concurrent_link_conflict'));
      }
      const operation = run(rawUrl).finally(() => {
        if (inFlight.get(rawUrl) === operation) {
          inFlight.delete(rawUrl);
        }
      });
      inFlight.set(rawUrl, operation);
      return operation;
    },
  });
}
