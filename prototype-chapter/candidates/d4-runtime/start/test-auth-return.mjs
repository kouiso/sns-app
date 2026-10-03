import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AuthReturnError,
  createAuthReturnProcessor,
  parseAuthReturnUrl,
} from './lib/auth-return.mjs';

const RETURN_BASE = 'snsapp://auth/return';
const signupUrl = (hash = 'signup-hash') =>
  `${RETURN_BASE}?token_hash=${encodeURIComponent(hash)}&type=signup`;
const recoveryUrl = (hash = 'recovery-hash') =>
  `${RETURN_BASE}?token_hash=${encodeURIComponent(hash)}&type=recovery`;

function confirmedUser(id = 'user-1') {
  return { id, email_confirmed_at: '2026-10-03T00:00:00.000Z' };
}

function expectParseError(url, code, base = RETURN_BASE) {
  assert.throws(
    () => parseAuthReturnUrl(url, base),
    (error) => error instanceof AuthReturnError && error.code === code,
  );
}

test('parses the two explicitly supported purposes', () => {
  assert.deepEqual(parseAuthReturnUrl(signupUrl('a+b/c'), RETURN_BASE), {
    tokenHash: 'a+b/c',
    type: 'signup',
  });
  assert.deepEqual(parseAuthReturnUrl(recoveryUrl(), RETURN_BASE), {
    tokenHash: 'recovery-hash',
    type: 'recovery',
  });
});

test('requires the configured scheme, host, port, and path exactly', () => {
  expectParseError('other://auth/return?token_hash=x&type=signup', 'return_target_mismatch');
  expectParseError('snsapp://evil/return?token_hash=x&type=signup', 'return_target_mismatch');
  expectParseError('snsapp://auth/other?token_hash=x&type=signup', 'return_target_mismatch');
  expectParseError(
    'https://local.test:444/return?token_hash=x&type=signup',
    'return_target_mismatch',
    'https://local.test:443/return',
  );
});

test('rejects query keys outside the closed contract', () => {
  expectParseError(`${signupUrl()}&next=/profile`, 'unexpected_query_parameter');
  expectParseError(`${signupUrl()}&access_token=bearer`, 'unexpected_query_parameter');
});

test('rejects duplicate security parameters regardless of ordering', () => {
  expectParseError(`${signupUrl()}&token_hash=second`, 'duplicate_query_parameter');
  expectParseError(`${recoveryUrl()}&type=signup`, 'duplicate_query_parameter');
});

test('rejects missing and unsupported purposes before auth', () => {
  expectParseError(`${RETURN_BASE}?token_hash=x`, 'missing_query_parameter');
  expectParseError(`${RETURN_BASE}?token_hash=x&type=magiclink`, 'unsupported_type');
});

test('rejects fragments including implicit bearer callbacks', () => {
  expectParseError(`${signupUrl()}#ignored`, 'fragment_not_allowed');
  expectParseError(
    `${RETURN_BASE}#access_token=secret&refresh_token=secret&type=recovery`,
    'fragment_not_allowed',
  );
});

test('rejects malformed percent escapes before parsing values', () => {
  expectParseError(`${RETURN_BASE}?token_hash=bad%2&type=signup`, 'malformed_percent_encoding');
  expectParseError(`${RETURN_BASE}?token_hash=bad%GG&type=signup`, 'malformed_percent_encoding');
});

test('rejects raw and decoded control characters', () => {
  expectParseError(`${RETURN_BASE}?token_hash=x\n&type=signup`, 'control_character');
  expectParseError(`${RETURN_BASE}?token_hash=x%0A&type=signup`, 'invalid_token_hash');
});

test('rejects configured bases that contain their own query or fragment', () => {
  expectParseError(signupUrl(), 'invalid_configuration', `${RETURN_BASE}?tenant=x`);
  expectParseError(signupUrl(), 'invalid_configuration', `${RETURN_BASE}#x`);
});

test('server verification receives only the parsed hash and purpose', async () => {
  const calls = [];
  const auth = {
    async verifyOtp(params) {
      calls.push(params);
      return { data: { user: confirmedUser(), session: { active: true } }, error: null };
    },
    async getUser() {
      return { data: { user: confirmedUser() }, error: null };
    },
  };
  const result = await createAuthReturnProcessor({ auth, returnBase: RETURN_BASE }).process(
    recoveryUrl('server-bound'),
  );
  assert.equal(result.status, 'approved');
  assert.equal(result.purpose, 'recovery');
  assert.deepEqual(calls, [{ token_hash: 'server-bound', type: 'recovery' }]);
});

test('concurrent delivery of one URL coalesces into one server verification', async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  let verifies = 0;
  const auth = {
    async verifyOtp() {
      verifies += 1;
      await gate;
      return { data: { user: confirmedUser(), session: {} }, error: null };
    },
    async getUser() {
      return { data: { user: confirmedUser() }, error: null };
    },
  };
  const processor = createAuthReturnProcessor({ auth, returnBase: RETURN_BASE });
  const first = processor.process(signupUrl());
  const second = processor.process(signupUrl());
  release();
  const [a, b] = await Promise.all([first, second]);
  assert.strictEqual(a, b);
  assert.equal(a.status, 'approved');
  assert.equal(verifies, 1);
});

test('a different link cannot start a second auth mutation concurrently', async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  let verifies = 0;
  const auth = {
    async verifyOtp() {
      verifies += 1;
      await gate;
      return { data: { user: confirmedUser(), session: {} }, error: null };
    },
    async getUser() {
      return { data: { user: confirmedUser() }, error: null };
    },
  };
  const processor = createAuthReturnProcessor({ auth, returnBase: RETURN_BASE });
  const first = processor.process(signupUrl('first'));
  const conflict = await processor.process(recoveryUrl('second'));
  assert.deepEqual(conflict, {
    status: 'rejected',
    code: 'concurrent_link_conflict',
    sessionMutated: false,
    reconciliationNeeded: false,
  });
  release();
  assert.equal((await first).status, 'approved');
  assert.equal(verifies, 1);
});

test('a completed URL never re-approves a route after logout', async () => {
  let verifies = 0;
  let reads = 0;
  const auth = {
    async verifyOtp() {
      verifies += 1;
      return verifies === 1
        ? { data: { user: confirmedUser(), session: {} }, error: null }
        : { data: { user: null, session: null }, error: { code: 'otp_expired' } };
    },
    async getUser() {
      reads += 1;
      return { data: { user: confirmedUser() }, error: null };
    },
  };
  const processor = createAuthReturnProcessor({ auth, returnBase: RETURN_BASE });
  assert.equal((await processor.process(recoveryUrl())).status, 'approved');
  assert.deepEqual(await processor.process(recoveryUrl()), {
    status: 'already_processed',
    code: 'already_processed',
    sessionMutated: false,
    reconciliationNeeded: false,
  });
  assert.equal(verifies, 1);
  assert.equal(reads, 1);
});

test('verification rejection cannot unlock recovery', async () => {
  let reads = 0;
  const auth = {
    async verifyOtp() {
      return { data: { user: null, session: null }, error: { code: 'otp_expired' } };
    },
    async getUser() {
      reads += 1;
      return { data: { user: confirmedUser() }, error: null };
    },
  };
  const result = await createAuthReturnProcessor({ auth, returnBase: RETURN_BASE }).process(
    recoveryUrl(),
  );
  assert.deepEqual(result, {
    status: 'rejected',
    code: 'verification_failed',
    sessionMutated: false,
    reconciliationNeeded: false,
  });
  assert.equal(reads, 0);
});

test('cross-purpose hash validation is left to the real server response', async () => {
  const calls = [];
  const auth = {
    async verifyOtp(params) {
      calls.push(params);
      return params.type === 'signup'
        ? { data: { user: null, session: null }, error: { code: 'otp_expired' } }
        : { data: { user: confirmedUser(), session: {} }, error: null };
    },
    async getUser() {
      return { data: { user: confirmedUser() }, error: null };
    },
  };
  const result = await createAuthReturnProcessor({ auth, returnBase: RETURN_BASE }).process(
    signupUrl('recovery-only-hash'),
  );
  assert.equal(result.status, 'rejected');
  assert.deepEqual(calls, [{ token_hash: 'recovery-only-hash', type: 'signup' }]);
});

test('authoritative user must match the server-verified user and be confirmed', async () => {
  const mismatched = createAuthReturnProcessor({
    returnBase: RETURN_BASE,
    auth: {
      async verifyOtp() {
        return { data: { user: confirmedUser('verified'), session: {} }, error: null };
      },
      async getUser() {
        return { data: { user: confirmedUser('different') }, error: null };
      },
    },
  });
  const mismatchResult = await mismatched.process(signupUrl('mismatch'));
  assert.equal(mismatchResult.status, 'reconciliation_needed');
  assert.equal(mismatchResult.code, 'authoritative_user_mismatch');

  const unconfirmed = createAuthReturnProcessor({
    returnBase: RETURN_BASE,
    auth: {
      async verifyOtp() {
        return { data: { user: { id: 'user-1' }, session: {} }, error: null };
      },
      async getUser() {
        return { data: { user: { id: 'user-1' } }, error: null };
      },
    },
  });
  const unconfirmedResult = await unconfirmed.process(signupUrl('unconfirmed'));
  assert.equal(unconfirmedResult.status, 'reconciliation_needed');
  assert.equal(unconfirmedResult.code, 'user_not_confirmed');
});

test('phone-only confirmation does not satisfy email confirmation', async () => {
  const processor = createAuthReturnProcessor({
    returnBase: RETURN_BASE,
    auth: {
      async verifyOtp() {
        return { data: { user: { id: 'user-1' }, session: {} }, error: null };
      },
      async getUser() {
        return {
          data: { user: { id: 'user-1', confirmed_at: '2026-10-03T00:00:00.000Z' } },
          error: null,
        };
      },
    },
  });
  const result = await processor.process(signupUrl('phone-only'));
  assert.equal(result.status, 'reconciliation_needed');
  assert.equal(result.code, 'user_not_confirmed');
});

test('a post-verification read failure is fail-closed and never caches recovery approval', async () => {
  let verifies = 0;
  let reads = 0;
  const auth = {
    async verifyOtp() {
      verifies += 1;
      return verifies === 1
        ? { data: { user: confirmedUser(), session: {} }, error: null }
        : { data: { user: null, session: null }, error: { code: 'otp_expired' } };
    },
    async getUser() {
      reads += 1;
      return { data: { user: null }, error: { code: 'network' } };
    },
  };
  const processor = createAuthReturnProcessor({ auth, returnBase: RETURN_BASE });
  const first = await processor.process(recoveryUrl('retryable'));
  assert.deepEqual(first, {
    status: 'reconciliation_needed',
    code: 'authoritative_user_unavailable',
    sessionMutated: true,
    reconciliationNeeded: true,
  });
  const second = await processor.process(recoveryUrl('retryable'));
  assert.equal(second.status, 'rejected');
  assert.equal(second.code, 'verification_failed');
  assert.equal(verifies, 2);
  assert.equal(reads, 1);
});

test('a thrown verification is treated as a possibly mutated session and never approves', async () => {
  const processor = createAuthReturnProcessor({
    returnBase: RETURN_BASE,
    auth: {
      async verifyOtp() {
        throw new Error('transport ended after request');
      },
      async getUser() {
        throw new Error('must not run');
      },
    },
  });
  assert.deepEqual(await processor.process(recoveryUrl('unknown-outcome')), {
    status: 'reconciliation_needed',
    code: 'verification_unavailable',
    sessionMutated: true,
    reconciliationNeeded: true,
  });
});

test('a verification response that reports mutation and error demands reconciliation', async () => {
  const auth = {
    async verifyOtp() {
      return {
        data: { user: confirmedUser(), session: { active: true } },
        error: { code: 'late_failure' },
      };
    },
    async getUser() {
      throw new Error('must not run');
    },
  };
  const result = await createAuthReturnProcessor({ auth, returnBase: RETURN_BASE }).process(
    recoveryUrl('late-failure'),
  );
  assert.deepEqual(result, {
    status: 'reconciliation_needed',
    code: 'verification_failed',
    sessionMutated: true,
    reconciliationNeeded: true,
  });
});
