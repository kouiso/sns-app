// Actual loopback GoTrue bearer validation with a deliberately in-memory REST seam.
// This is not supabase-js setSession, native linking, or persistence.
import { createAuthReturnHandler } from './auth_return.mjs';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const fixture = JSON.parse(input);
if (fixture.base !== 'http://127.0.0.1:54321') throw new Error('loopback_required');
const redirectTo = 'http://127.0.0.1:3000/';
const checks = [];
const check = (name, passed, facts = {}) => checks.push({ name, passed: !!passed, ...facts });

function makeAdapter() {
  let bearer = null;
  let calls = 0;
  let validations = 0;
  async function readUser(token) {
    const response = await fetch(fixture.base + '/auth/v1/user', {
      headers: { apikey: fixture.key, Authorization: 'Bearer ' + token },
      signal: AbortSignal.timeout(5000),
    });
    validations += 1;
    if (!response.ok) return { data: { user: null }, error: { code: 'rejected' } };
    const user = await response.json();
    return { data: { user }, error: null };
  }
  const auth = {
    async setSession({ access_token }) {
      calls += 1;
      const validated = await readUser(access_token);
      if (validated.error) return { data: { session: null }, error: { code: 'rejected' } };
      bearer = access_token;
      return { data: { session: { user: validated.data.user } }, error: null };
    },
    async getUser() { return readUser(bearer); },
  };
  return { handle: createAuthReturnHandler({ redirectTo, auth }),
           facts: () => ({ auth_mutations: calls, server_user_reads: validations }) };
}

const confirmedURL = new URL(fixture.confirmed);
check('actual_confirmation_callback_type',
      new URLSearchParams(confirmedURL.hash.slice(1)).get('type') === 'signup');
const success = makeAdapter();
const accepted = await success.handle(fixture.confirmed);
check('real_server_confirmed_session', accepted.ok === true &&
      accepted.assurance === 'confirmed-session' && accepted.route === 'profile-setup',
      success.facts());
const repeat = await success.handle(fixture.confirmed);
check('repeated_success_cannot_reauthorize_from_cache',
      repeat.ok === false && repeat.code === 'already_processed', success.facts());

const malformed = new URL(fixture.confirmed);
const malformedParams = new URLSearchParams(malformed.hash.slice(1));
malformedParams.set('access_token', 'not-a-valid-server-token');
malformed.hash = malformedParams.toString();
const invalid = makeAdapter();
const rejectedToken = await invalid.handle(malformed.href);
check('real_server_rejects_forged_bearer', rejectedToken.ok === false &&
      rejectedToken.code === 'set_session_failed', invalid.facts());

const reused = makeAdapter();
const rejectedUsed = await reused.handle(fixture.reused);
check('reused_email_link_rejected_before_session_mutation',
      rejectedUsed.ok === false && rejectedUsed.code === 'provider_error' &&
      reused.facts().auth_mutations === 0, reused.facts());

for (const [name, value] of [
  ['recovery_link_requires_purpose_proof', fixture.recovery],
  ['tampered_signup_type_cannot_prove_recovery', (() => {
    const url = new URL(fixture.confirmed);
    const parameters = new URLSearchParams(url.hash.slice(1));
    parameters.set('type', 'recovery');
    url.hash = parameters.toString();
    return url.href;
  })()],
]) {
  const adapter = makeAdapter();
  const rejected = await adapter.handle(value);
  check(name, rejected.ok === false && rejected.code === 'recovery_purpose_unverified' &&
        adapter.facts().auth_mutations === 0, adapter.facts());
}

const target = new URL(fixture.confirmed);
target.hostname = 'example.invalid';
const wrong = makeAdapter();
const wrongResult = await wrong.handle(target.href);
check('wrong_callback_target_no_auth_mutation', wrongResult.ok === false &&
      wrongResult.code === 'redirect_mismatch' && wrong.facts().auth_mutations === 0, wrong.facts());

const output = { scope: 'REST_ADAPTER_NOT_SDK_OR_APP', checks };
// Fail before stdout if any opaque credential or mail link would be serialized.
const serialized = JSON.stringify(output);
for (const sensitive of [fixture.confirmed, fixture.reused, fixture.recovery,
                        ...new URLSearchParams(confirmedURL.hash.slice(1))
                          .getAll('access_token'),
                        ...new URLSearchParams(confirmedURL.hash.slice(1))
                          .getAll('refresh_token')]) {
  if (sensitive && serialized.includes(sensitive)) throw new Error('redaction_failure');
}
process.stdout.write(serialized + '\n');
