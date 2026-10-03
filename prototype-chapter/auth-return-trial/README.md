# F11 implicit auth-return receiver trial

This directory is a bounded, non-formal candidate for the F11 receiver described in
`material/04_詳細設計書.md` §1.4, §2.2, and §9.2. It does not settle B5 or B18. It is
not an Expo/App/device integration and is not a complete Supabase client.

## API and supported shape

```js
const handleAuthReturn = createAuthReturnHandler({
  redirectTo: 'myapp://auth/return',
  auth: { setSession, getUser },
  verifyRecoveryPurpose, // optional trusted proof seam; required for recovery
});

const result = await handleAuthReturn(receivedURL);
```

`redirectTo` is one exact configured scheme + host (including port) + path. HTTPS and
custom schemes are accepted. Cleartext HTTP is accepted only for `localhost` and
`127.0.0.1` test adapters. The configured value may not contain credentials, a query,
or a fragment.

The receiver supports the implicit-token parameter shape with a closed `type` set:
`signup` and `recovery`. PKCE `code` returns `unsupported_pkce_flow`; deciding whether
the production flow is implicit or PKCE remains part of B18. Parameters may be in the
query or fragment, but auth-control parameters in both locations are rejected. Duplicate
decoded keys, malformed percent encoding, provider errors, missing tokens, and a target
that differs from `redirectTo` are rejected before auth mutation.

Tokens are opaque inputs. Their spelling or JWT shape never authenticates a user. The
receiver calls injected `auth.setSession`, then authoritative `auth.getUser`, and requires
the returned user ID to equal `setSession`'s session user ID. Signup additionally requires
a nonempty `email_confirmed_at`. This establishes a confirmed session; it does not prove
that the bearer tokens came from a particular email-link event. The returned `flow` is
a routing hint, not proof of new signup; profile setup must safely handle existing profiles.

The URL `type` value is attacker-modifiable and `getUser` does not establish recovery
purpose. Recovery therefore fails with `recovery_purpose_unverified` before `setSession`
unless `verifyRecoveryPurpose` independently proves the purpose. The verifier receives
the two opaque tokens and must consult a trustworthy server-issued or server-validated
signal; returning true based on the URL `type`, token shape, or `getUser` repeats the same
trust mistake. The exact production proof and flow remain unspecified under B18.

## Race, retry, and data handling

Simultaneous delivery of the same URL shares one promise. Successful URLs are remembered
by bounded SHA-256 fingerprints, and a warm duplicate returns `already_processed` as an
ignore signal. It never repeats a cached successful route decision because the user may
have signed out or switched accounts since the first delivery. Failures are not cached,
allowing an explicit retry. A different URL arriving while auth mutation is in flight
receives `concurrent_link_conflict`; it does not race a second `setSession`.

Results contain only small codes or fixed routing metadata. They contain no raw URL,
token, provider payload, or user ID, and this module performs no logging. The injected
auth and recovery verifier necessarily receive tokens and must apply the same redaction.

`setSession` may mutate persisted auth state before `getUser` fails. The receiver reports
`get_user_failed` but deliberately does not call `signOut`: blindly signing out could
destroy a session that existed before a malformed or failing return. Production session
rollback/reconciliation needs an explicit client-level design. The successful duplicate
cache is process-local, so it covers warm delivery only; a cold start validates again.
This suppresses duplicate delivery, not token replay: reordering parameters produces a
different fingerprint. The two callers of a shared in-flight promise must also apply one
navigation effect; sharing the auth operation does not navigate the UI for them.

This Node trial uses `node:crypto` for fingerprints and Node's WHATWG `URL` behavior.
It does not prove React Native URL-polyfill behavior, Expo linking delivery, cold-start
hooks, development-build redirects, device behavior, Supabase session persistence, or
full Supabase SDK integration. Stable auth redirects require a development build per the
Expo linking constraint supplied with this trial; B5/B18 remain open.

## Test

Run with Node 22 and no installed dependencies:

```sh
node --test test_auth_return.mjs
```

## Dedicated local server probe

`measure_local.py` uses only the existing loopback `sns-trio-local` stack, checks its
port bindings, and creates a synthetic Mailpit user. It does not provision a cloud
project or send external mail. Choose an unused output path and an explicit Node 22:

```sh
python3 measure_local.py --cli /path/to/supabase --node /path/to/node22 \
  --output /tmp/new-auth-return-measurement.json
```

The child `local_adapter.mjs` stores a bearer in memory and calls the real GoTrue
`/auth/v1/user` endpoint. `set_session_calls` counts attempted adapter calls, not successful
state mutations. Two successful user reads do not prove Supabase SDK behavior. Opaque
credentials and callbacks travel only through stdin/memory; output contains fixed
check names, booleans, counts, and source hashes. The final redaction check examines
all three callbacks and their individual query/fragment token values. Synthetic
accounts remain in the disposable local stack. This is a production-side probe,
not a learner Docker setup or a completed email-to-app lesson.
