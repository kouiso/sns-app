import test from 'node:test';
import assert from 'node:assert/strict';

import { createAuthReturnHandler } from './auth_return.mjs';

const redirectTo = 'myapp://auth/return';
const accessToken = 'opaque-access-token';
const refreshToken = 'opaque-refresh-token';

function link({ type = 'signup', access = accessToken, refresh = refreshToken } = {}) {
  return `${redirectTo}#access_token=${access}&refresh_token=${refresh}&type=${type}`;
}

function verifiedAuth(overrides = {}) {
  const calls = { setSession: 0, getUser: 0 };
  const auth = {
    async setSession(tokens) {
      calls.setSession += 1;
      assert.deepEqual(tokens, {
        access_token: accessToken,
        refresh_token: refreshToken,
      });
      return {
        data: { session: { user: { id: 'user-1' } } },
        error: null,
      };
    },
    async getUser() {
      calls.getUser += 1;
      return {
        data: {
          user: { id: 'user-1', email_confirmed_at: '2026-10-03T00:00:00Z' },
        },
        error: null,
      };
    },
    ...overrides,
  };
  return { auth, calls };
}

function assertSanitized(result) {
  const serialized = JSON.stringify(result);
  assert.doesNotMatch(serialized, /opaque-|myapp:|user-1|provider exploded/i);
}

test('accepts a verified, confirmed signup session', async () => {
  const { auth, calls } = verifiedAuth();
  const handle = createAuthReturnHandler({ redirectTo, auth });

  const result = await handle(link());

  assert.deepEqual(result, {
    ok: true,
    flow: 'signup',
    route: 'profile-setup',
    assurance: 'confirmed-session',
  });
  assert.deepEqual(calls, { setSession: 1, getUser: 1 });
  assertSanitized(result);
});

test('accepts recovery only with independent trusted purpose proof', async () => {
  const { auth } = verifiedAuth();
  let proofCalls = 0;
  const handle = createAuthReturnHandler({
    redirectTo,
    auth,
    verifyRecoveryPurpose: async ({ accessToken: access, refreshToken: refresh }) => {
      proofCalls += 1;
      assert.equal(access, accessToken);
      assert.equal(refresh, refreshToken);
      return true;
    },
  });

  const result = await handle(link({ type: 'recovery' }));

  assert.equal(result.ok, true);
  assert.equal(result.route, 'password-reset');
  assert.equal(result.assurance, 'trusted-purpose-and-verified-session');
  assert.equal(proofCalls, 1);
  assertSanitized(result);
});

test('refuses a recovery hint without purpose proof and does not mutate auth', async () => {
  const { auth, calls } = verifiedAuth();
  const handle = createAuthReturnHandler({ redirectTo, auth });

  assert.deepEqual(await handle(link({ type: 'recovery' })), {
    ok: false,
    code: 'recovery_purpose_unverified',
  });
  assert.deepEqual(calls, { setSession: 0, getUser: 0 });
});

test('changing an otherwise valid signup URL type to recovery earns no recovery authority', async () => {
  const { auth, calls } = verifiedAuth();
  const handle = createAuthReturnHandler({
    redirectTo,
    auth,
    verifyRecoveryPurpose: async () => false,
  });

  const tampered = link().replace('type=signup', 'type=recovery');
  assert.equal((await handle(tampered)).code, 'recovery_purpose_unverified');
  assert.deepEqual(calls, { setSession: 0, getUser: 0 });
});

test('rejects malformed, control-whitespace, and invalid-percent URLs', async () => {
  const { auth } = verifiedAuth();
  const handle = createAuthReturnHandler({ redirectTo, auth });

  assert.equal((await handle('not a URL')).code, 'invalid_url');
  assert.equal((await handle(`\n${link()}`)).code, 'invalid_url');
  assert.equal(
    (await handle(`${redirectTo}#access_token=%GG&refresh_token=x&type=signup`)).code,
    'invalid_percent_encoding',
  );
});

test('requires exact configured scheme, host, port, and path', async () => {
  const { auth } = verifiedAuth();
  const handle = createAuthReturnHandler({ redirectTo, auth });

  assert.equal((await handle(link().replace('/return', '/other'))).code, 'redirect_mismatch');
  assert.equal((await handle(link().replace('myapp:', 'other:'))).code, 'redirect_mismatch');
});

test('rejects auth controls split between query and fragment', async () => {
  const { auth } = verifiedAuth();
  const handle = createAuthReturnHandler({ redirectTo, auth });

  const result = await handle(
    `${redirectTo}?access_token=${accessToken}#refresh_token=${refreshToken}&type=signup`,
  );
  assert.equal(result.code, 'ambiguous_parameter_location');
});

test('rejects duplicate decoded parameters, including encoded duplicate keys', async () => {
  const { auth } = verifiedAuth();
  const handle = createAuthReturnHandler({ redirectTo, auth });

  const result = await handle(
    `${redirectTo}#access_token=a&%61ccess_token=b&refresh_token=c&type=signup`,
  );
  assert.equal(result.code, 'duplicate_parameter');
});

test('maps provider payloads to one sanitized error code', async () => {
  const { auth } = verifiedAuth();
  const handle = createAuthReturnHandler({ redirectTo, auth });

  const result = await handle(
    `${redirectTo}#error=access_denied&error_description=provider%20exploded`,
  );
  assert.deepEqual(result, { ok: false, code: 'provider_error' });
  assertSanitized(result);
});

test('fails closed for PKCE code flow and unsupported event types', async () => {
  const { auth } = verifiedAuth();
  const handle = createAuthReturnHandler({ redirectTo, auth });

  assert.equal((await handle(`${redirectTo}?code=secret-code`)).code, 'unsupported_pkce_flow');
  assert.equal((await handle(link({ type: 'email' }))).code, 'unsupported_type');
});

test('requires both opaque tokens without treating their shape as authentication', async () => {
  const { auth } = verifiedAuth({
    async setSession() {
      return { data: { session: null }, error: null };
    },
  });
  const handle = createAuthReturnHandler({ redirectTo, auth });

  assert.equal(
    (await handle(`${redirectTo}#access_token=${accessToken}&type=signup`)).code,
    'missing_tokens',
  );
  assert.equal((await handle(link())).code, 'missing_session');
});

test('sanitizes setSession backend errors and permits a retry', async () => {
  let attempts = 0;
  const { auth } = verifiedAuth({
    async setSession() {
      attempts += 1;
      if (attempts === 1) return { data: null, error: new Error('provider exploded') };
      return { data: { session: { user: { id: 'user-1' } } }, error: null };
    },
  });
  const handle = createAuthReturnHandler({ redirectTo, auth });

  const first = await handle(link());
  const second = await handle(link());
  assert.deepEqual(first, { ok: false, code: 'set_session_failed' });
  assert.equal(second.ok, true);
  assert.equal(attempts, 2);
  assertSanitized(first);
});

test('distinguishes getUser failure after setSession may have mutated auth state', async () => {
  const { auth, calls } = verifiedAuth({
    async getUser() {
      calls.getUser += 1;
      return { data: null, error: new Error('provider exploded') };
    },
  });
  const handle = createAuthReturnHandler({ redirectTo, auth });

  const result = await handle(link());
  assert.deepEqual(result, { ok: false, code: 'get_user_failed' });
  assert.deepEqual(calls, { setSession: 1, getUser: 1 });
  assertSanitized(result);
});

test('rejects a missing or non-string authoritative email confirmation time', async () => {
  const { auth } = verifiedAuth({
    async getUser() {
      return { data: { user: { id: 'user-1', email_confirmed_at: null } }, error: null };
    },
  });
  const handle = createAuthReturnHandler({ redirectTo, auth });

  assert.equal((await handle(link())).code, 'email_not_confirmed');

  const second = createAuthReturnHandler({
    redirectTo,
    auth: verifiedAuth({
      async getUser() {
        return { data: { user: { id: 'user-1', email_confirmed_at: true } }, error: null };
      },
    }).auth,
  });
  assert.equal((await second(link())).code, 'email_not_confirmed');
});

test('rejects identity mismatch between the session and authoritative getUser result', async () => {
  const { auth } = verifiedAuth({
    async getUser() {
      return {
        data: { user: { id: 'user-2', email_confirmed_at: '2026-10-03T00:00:00Z' } },
        error: null,
      };
    },
  });
  const handle = createAuthReturnHandler({ redirectTo, auth });

  assert.equal((await handle(link())).code, 'user_identity_mismatch');
});

test('coalesces an in-flight duplicate but never re-authorizes routing from a warm cache', async () => {
  let release;
  let externallySignedOut = false;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const { auth, calls } = verifiedAuth({
    async setSession(tokens) {
      calls.setSession += 1;
      await gate;
      return { data: { session: { user: { id: 'user-1' } } }, error: null };
    },
    async getUser() {
      calls.getUser += 1;
      if (externallySignedOut) return { data: null, error: new Error('signed out') };
      return {
        data: {
          user: { id: 'user-1', email_confirmed_at: '2026-10-03T00:00:00Z' },
        },
        error: null,
      };
    },
  });
  const handle = createAuthReturnHandler({ redirectTo, auth });

  const first = handle(link());
  const same = handle(link());
  assert.strictEqual(first, same);
  release();
  const [firstResult, sameResult] = await Promise.all([first, same]);
  assert.strictEqual(firstResult, sameResult);
  externallySignedOut = true;
  const afterSignOut = await handle(link());
  assert.deepEqual(afterSignOut, { ok: false, code: 'already_processed' });
  assert.notEqual(afterSignOut.ok, true);
  assert.deepEqual(calls, { setSession: 1, getUser: 1 });
});

test('rejects a competing link while one auth mutation is active', async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const { auth, calls } = verifiedAuth({
    async setSession() {
      calls.setSession += 1;
      await gate;
      return { data: { session: { user: { id: 'user-1' } } }, error: null };
    },
  });
  const handle = createAuthReturnHandler({ redirectTo, auth });

  const first = handle(link());
  const competing = await handle(link({ access: 'different-access' }));
  assert.deepEqual(competing, { ok: false, code: 'concurrent_link_conflict' });
  release();
  assert.equal((await first).ok, true);
  assert.equal(calls.setSession, 1);
});

test('allows HTTP only for explicit localhost or 127.0.0.1 trial redirects', () => {
  const { auth } = verifiedAuth();
  assert.doesNotThrow(() =>
    createAuthReturnHandler({ redirectTo: 'http://127.0.0.1:54321/auth/return', auth }),
  );
  assert.throws(() =>
    createAuthReturnHandler({ redirectTo: 'http://example.com/auth/return', auth }),
  );
});
