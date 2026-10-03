import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createExclusiveOperation,
  createLatestRequestGuard,
  createProfileRepository,
  profilePayload,
} from './lib/profile-flow.mjs';

function clientFor({ updateResult, rereadResult }) {
  const observed = { payload: null, filters: [] };
  return {
    observed,
    from(table) {
      assert.equal(table, 'users');
      return {
        update(payload) {
          observed.payload = payload;
          return {
            eq(column, value) {
              observed.filters.push([column, value]);
              return { select: () => ({ abortSignal: async () => updateResult }) };
            },
          };
        },
        select() {
          return {
            eq(column, value) {
              observed.filters.push([column, value]);
              return { maybeSingle: () => ({ abortSignal: async () => rereadResult }) };
            },
          };
        },
      };
    },
  };
}

test('save sends only allowlisted profile fields and confirms with a fresh own-row read', async () => {
  const client = clientFor({
    updateResult: { data: [{ id: 'A' }], error: null },
    rereadResult: { data: { id: 'A', username: 'alice', display_name: 'Alice', bio: 'hi' }, error: null },
  });
  const result = await createProfileRepository(client).save('A', {
    username: ' alice ', displayName: ' Alice ', bio: 'hi', id: 'B', created_at: 'forbidden',
  });
  assert.deepEqual(client.observed.payload, { username: 'alice', display_name: 'Alice', bio: 'hi' });
  assert.deepEqual(client.observed.filters, [['id', 'A'], ['id', 'A']]);
  assert.equal(result.status, 'saved');
});

test('zero-row update is not reported as saved and does not perform a confirmation read', async () => {
  const client = clientFor({ updateResult: { data: [], error: null }, rereadResult: { data: null, error: null } });
  const result = await createProfileRepository(client).save('A', { username: 'alice', displayName: 'Alice', bio: '' });
  assert.equal(result.status, 'zero_rows');
  assert.deepEqual(client.observed.filters, [['id', 'A']]);
});

test('late results are rejected after session switch and after unmount', () => {
  const guard = createLatestRequestGuard('A');
  const a = guard.begin();
  guard.switchUser('B');
  assert.equal(guard.accepts(a), false);
  const b = guard.begin();
  assert.equal(guard.accepts(b), true);
  guard.dispose();
  assert.equal(guard.accepts(b), false);
  guard.switchUser('B');
  const strictModeRemount = guard.begin();
  assert.equal(guard.accepts(strictModeRemount), true);
  assert.equal(guard.accepts(b), false);
});

test('exclusive operation rejects duplicate save until the first one finishes', () => {
  const operation = createExclusiveOperation();
  assert.equal(operation.begin(), true);
  assert.equal(operation.begin(), false);
  operation.finish();
  assert.equal(operation.begin(), true);
});

test('profile payload cannot be expanded by caller-owned fields', () => {
  assert.deepEqual(
    profilePayload({ username: 'u', displayName: 'n', bio: '', id: 'other', updated_at: 'forbidden' }),
    { username: 'u', display_name: 'n', bio: null },
  );
});

test('transport failure after an update starts is reported as unconfirmed', async () => {
  const client = clientFor({ updateResult: null, rereadResult: null });
  client.from = () => ({
    update: () => ({
      eq: () => ({
        select: () => ({ abortSignal: async () => { throw new Error('connection lost'); } }),
      }),
    }),
  });
  const result = await createProfileRepository(client).save('A', { username: 'alice', displayName: 'Alice', bio: '' });
  assert.equal(result.status, 'unconfirmed');
});

test('a mismatched confirmation read cannot turn an update into saved', async () => {
  const client = clientFor({
    updateResult: { data: [{ id: 'A' }], error: null, status: 200 },
    rereadResult: { data: { id: 'A', username: 'alice', display_name: 'Old', bio: null }, error: null },
  });
  const result = await createProfileRepository(client).save('A', { username: 'alice', displayName: 'Alice', bio: '' });
  assert.equal(result.status, 'unconfirmed');
});

test('a profile read is aborted at its bounded timeout', async () => {
  const client = {
    from: () => ({
      select: () => ({
        eq: () => ({
          maybeSingle: () => ({
            abortSignal: (signal) => new Promise((_, reject) => {
              signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
            }),
          }),
        }),
      }),
    }),
  };
  const result = await createProfileRepository(client, { timeoutMs: 5 }).read('A');
  assert.equal(result.status, 'error');
});

test('a malformed or multi-row update response is never called zero rows or saved', async () => {
  const malformed = clientFor({ updateResult: null, rereadResult: { data: null, error: null } });
  const malformedResult = await createProfileRepository(malformed).save('A', { username: 'alice', displayName: 'Alice', bio: '' });
  assert.equal(malformedResult.status, 'unconfirmed');

  const multi = clientFor({ updateResult: { data: [{ id: 'A' }, { id: 'B' }], error: null }, rereadResult: { data: null, error: null } });
  const multiResult = await createProfileRepository(multi).save('A', { username: 'alice', displayName: 'Alice', bio: '' });
  assert.equal(multiResult.status, 'unconfirmed');
});

test('a read cannot bind a different user profile to the current session', async () => {
  const client = clientFor({
    updateResult: null,
    rereadResult: { data: { id: 'B', username: 'bob', display_name: 'Bob', bio: null }, error: null },
  });
  const result = await createProfileRepository(client).read('A');
  assert.equal(result.status, 'error');
});
