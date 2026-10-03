#!/usr/bin/env node
/**
 * Real Supabase-JS verifier for the non-formal D4 predecessor candidate.
 *
 * It accepts dedicated local CLI status JSON only on stdin. Credentials,
 * synthetic identities, JWTs, token hashes, URLs, and row identifiers stay in
 * memory and are rejected by a final redaction guard before report writing.
 */
import { createHash, randomBytes, randomUUID } from 'node:crypto'
import { closeSync, openSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { performance } from 'node:perf_hooks'
import { spawnSync } from 'node:child_process'

const require = createRequire(new URL('../auth-sdk57/package.json', import.meta.url))
const { createClient } = require('@supabase/supabase-js')
const sdkVersion = require('@supabase/supabase-js/package.json').version

const here = dirname(fileURLToPath(import.meta.url))
const migrationDirectory = resolve(here, 'supabase/migrations')
const expectedMigrationManifest = Object.freeze([
  Object.freeze({
    name: '20261003080326_d4_predecessor_candidate.sql',
    sha256: 'e4667d31b9beff022b56a030ef4f0c26f924224c1170b2285bdda823d2c109b4',
  }),
  Object.freeze({
    name: '20261003081350_d4_remove_unneeded_parent_definer.sql',
    sha256: '5684db307ec7f1cf873032465fa9cbb9f7f14dd264effbbd509792a51c2795c4',
  }),
  Object.freeze({
    name: '20261003081937_d4_align_notification_update_visibility.sql',
    sha256: 'b493ec015eaf4f98a1ddb453ceb839caa232ee17b6043cfe3b7cc0cef5f75f7b',
  }),
])
const expectedSdkVersion = '2.117.2'
const expectedApiUrl = 'http://127.0.0.1:54321'
const mailpitUrl = 'http://127.0.0.1:54324'
const databaseContainer = 'supabase_db_sns-trio-local'
const tables = ['users', 'posts', 'post_media', 'likes', 'follows', 'notifications', 'hashtags', 'post_hashtags', 'bookmarks']

const checks = []
const clients = []
const sensitiveValues = new Set()
const cleanup = {
  scope: 'local_client_session_only',
  attempted: 0,
  succeeded: 0,
  failed: 0,
  access_jwt_revocation_measured: false,
}
const startedAtUtc = new Date().toISOString()
const startedMonotonic = performance.now()
let currentStep = 'argument_validation'
let outputFd

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

function migrationManifest() {
  const actual = readdirSync(migrationDirectory)
    .filter((name) => name.endsWith('.sql'))
    .sort()
    .map((name) => ({ name, sha256: sha256(readFileSync(resolve(migrationDirectory, name))) }))
  if (JSON.stringify(actual) !== JSON.stringify(expectedMigrationManifest)) {
    throw new Error('migration manifest changed')
  }
  return actual
}

function localAuthSafetyFlags() {
  const content = readFileSync('/tmp/sns-trio-local/supabase/config.toml', 'utf8')
  let section = ''
  let anonymousSignIns
  let emailConfirmations
  for (const line of content.split(/\r?\n/)) {
    const sectionMatch = line.match(/^\s*\[([^\]]+)]\s*$/)
    if (sectionMatch) {
      section = sectionMatch[1]
      continue
    }
    const setting = line.match(/^\s*([a-z_]+)\s*=\s*(true|false)\s*$/)
    if (!setting) continue
    if (section === 'auth' && setting[1] === 'enable_anonymous_sign_ins') anonymousSignIns = setting[2] === 'true'
    if (section === 'auth.email' && setting[1] === 'enable_confirmations') emailConfirmations = setting[2] === 'true'
  }
  return { emailConfirmations, anonymousSignIns }
}

function rememberSensitive(...values) {
  for (const value of values) {
    if (typeof value === 'string' && value.length >= 8) sensitiveValues.add(value)
  }
}

function serializeReport(report) {
  const rendered = `${JSON.stringify(report, null, 2)}\n`
  for (const secret of sensitiveValues) {
    if (rendered.includes(secret)) throw new Error('redaction guard rejected report')
  }
  return rendered
}

function fixedFailureKind(error) {
  if (error instanceof SyntaxError) return 'invalid_json'
  if (error instanceof TypeError) return 'type_error'
  if (error && typeof error === 'object' && error.name === 'AbortError') return 'timeout'
  return 'measurement_error'
}

function parseArguments(argv) {
  if (argv.length !== 2 || argv[0] !== '--output' || !argv[1]) {
    throw new Error('expected --output with a fresh path')
  }
  return resolve(argv[1])
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf8',
    maxBuffer: 1024 * 1024,
    ...options,
  })
  if (result.status !== 0 || result.error) throw new Error('subprocess failed')
  return result.stdout.trim()
}

function psql(sql) {
  return run(
    'docker',
    ['exec', '-i', databaseContainer, 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-v', 'ON_ERROR_STOP=1'],
    { input: `${sql.trim()}\n` },
  )
}

function record(label, passed, facts = {}) {
  checks.push({ label, passed: Boolean(passed), ...facts })
}

function dataShape(data) {
  if (data === null) return 'null'
  if (data === true) return 'boolean_true'
  if (data === false) return 'boolean_false'
  if (Number.isInteger(data)) return 'integer'
  if (Array.isArray(data)) return `array_${data.length}`
  return typeof data === 'object' ? 'object' : typeof data
}

function sdkFacts(response, dbStateOk) {
  return {
    status: Number.isInteger(response?.status) ? response.status : response?.error ? 'sdk_error' : 'sdk_success',
    code: response?.error?.code ?? null,
    count: Number.isInteger(response?.count) ? response.count : null,
    data_shape: dataShape(response?.data ?? null),
    db_state_ok: Boolean(dbStateOk),
  }
}

function expected(response, { status, code = null, shape, count = null }) {
  return response.status === status && (response.error?.code ?? null) === code &&
    dataShape(response.data) === shape && response.count === count
}

function assertUuid(value) {
  if (typeof value !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) {
    throw new Error('invalid UUID')
  }
  return value
}

function sqlUuid(value) {
  return `'${assertUuid(value)}'::uuid`
}

function assertTimestamp(value) {
  if (typeof value !== 'string' || Number.isNaN(Date.parse(value)) || !/^\d{4}-\d{2}-\d{2}T/.test(value)) {
    throw new Error('invalid timestamp')
  }
  return value
}

function jwtPayload(token) {
  if (typeof token !== 'string' || token.startsWith('sb_secret_')) throw new Error('legacy JWT required')
  const parts = token.split('.')
  if (parts.length !== 3) throw new Error('legacy JWT required')
  const value = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'))
  if (!value || typeof value !== 'object') throw new Error('invalid JWT payload')
  return value
}

async function boundedFetch(input, init = {}) {
  const controller = new AbortController()
  const upstream = init.signal
  const abortFromUpstream = () => controller.abort(upstream?.reason)
  if (upstream?.aborted) abortFromUpstream()
  else upstream?.addEventListener('abort', abortFromUpstream, { once: true })
  const timer = setTimeout(() => controller.abort(), 15_000)
  try {
    return await globalThis.fetch(input, { ...init, signal: controller.signal })
  } finally {
    clearTimeout(timer)
    upstream?.removeEventListener('abort', abortFromUpstream)
  }
}

function makeClient(apiUrl, anonKey, track = false) {
  const client = createClient(apiUrl, anonKey, {
    global: { fetch: boundedFetch },
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  })
  if (track) clients.push(client)
  return client
}

async function cleanupLocalSessions() {
  cleanup.attempted = clients.length
  for (const client of clients) {
    try {
      const result = await client.auth.signOut({ scope: 'local' })
      if (result.error) cleanup.failed += 1
      else cleanup.succeeded += 1
    } catch {
      cleanup.failed += 1
    }
  }
}

async function fetchJson(url) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 10_000)
  try {
    const response = await globalThis.fetch(url, { signal: controller.signal, redirect: 'error' })
    if (!response.ok) throw new Error('local endpoint failed')
    return await response.json()
  } finally {
    clearTimeout(timer)
  }
}

async function signupTokenHash(email) {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    const listing = await fetchJson(`${mailpitUrl}/api/v1/messages`)
    const matches = (listing.messages ?? []).filter((message) =>
      (message.To ?? []).some((recipient) => recipient.Address === email),
    )
    if (matches.length > 0) {
      rememberSensitive(matches[0].ID)
      const message = await fetchJson(`${mailpitUrl}/api/v1/message/${encodeURIComponent(matches[0].ID)}`)
      const hrefs = [...String(message.HTML ?? '').matchAll(/href="([^"]+)"/g)]
        .map((match) => match[1].replaceAll('&amp;', '&'))
      for (const href of hrefs) {
        rememberSensitive(href)
        const candidate = new URL(href)
        if (candidate.origin === expectedApiUrl && candidate.pathname === '/auth/v1/verify' &&
            candidate.searchParams.get('type') === 'signup' && candidate.searchParams.has('token')) {
          const token = candidate.searchParams.get('token')
          rememberSensitive(token)
          return token
        }
      }
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 100))
  }
  throw new Error('confirmation message unavailable')
}

async function createConfirmedUser(apiUrl, anonKey, label) {
  const client = makeClient(apiUrl, anonKey, true)
  const email = `d4-${randomBytes(12).toString('hex')}-${label}@example.test`
  const password = randomBytes(24).toString('base64url')
  rememberSensitive(email, password)
  const signup = await client.auth.signUp({ email, password })
  rememberSensitive(signup.data.user?.id)
  const signupOk = !signup.error && Boolean(signup.data.user?.id) && !signup.data.session
  const profileTriggered = signupOk && psql(`select count(*) from public.users where id=${sqlUuid(signup.data.user?.id)};`) === '1'
  record(`auth_${label}_signup_profile_triggered`, profileTriggered, {
    status: signup.error ? 'sdk_error' : 'sdk_success',
    code: signup.error?.code ?? null,
    count: null,
    data_shape: signup.data.session ? 'session_present' : 'session_absent',
    db_state_ok: profileTriggered,
  })
  if (!signupOk) throw new Error('signup failed')
  const tokenHash = await signupTokenHash(email)
  const verified = await client.auth.verifyOtp({ token_hash: tokenHash, type: 'signup' })
  rememberSensitive(verified.data.user?.id, verified.data.session?.access_token, verified.data.session?.refresh_token)
  const userId = assertUuid(verified.data.user?.id)
  const authoritative = await client.auth.getUser()
  rememberSensitive(authoritative.data.user?.id)
  const profileStillPresent = psql(`select count(*) from public.users where id=${sqlUuid(userId)};`) === '1'
  const ordinary = !verified.error && !authoritative.error && authoritative.data.user?.id === userId &&
    typeof authoritative.data.user?.email_confirmed_at === 'string' &&
    jwtPayload(verified.data.session?.access_token).role === 'authenticated' && profileStillPresent
  record(`auth_${label}_ordinary_authenticated_role`, ordinary, {
    status: verified.error ? 'sdk_error' : 'sdk_success',
    code: verified.error?.code ?? authoritative.error?.code ?? null,
    count: null,
    data_shape: verified.data.session ? 'verified_authenticated_session' : 'session_absent',
    db_state_ok: profileStillPresent,
  })
  if (!ordinary) throw new Error('ordinary user verification failed')
  return { client, userId }
}

function catalogSnapshot() {
  const tableList = tables.map((name) => `'${name}'`).join(',')
  const raw = psql(`
    with minimums as (
      select jsonb_build_object(
        'nine_rls', (
          select count(*) = 9 and bool_and(c.relrowsecurity)
          from pg_class c join pg_namespace n on n.oid=c.relnamespace
          where n.nspname='public' and c.relname in (${tableList}) and c.relkind='r'
        ),
        'authenticated_bypass', (select rolbypassrls from pg_roles where rolname='authenticated'),
        'anon_no_dml', (
          select bool_and(
            not has_table_privilege('anon', format('public.%I', relname), 'SELECT') and
            not has_table_privilege('anon', format('public.%I', relname), 'INSERT') and
            not has_table_privilege('anon', format('public.%I', relname), 'UPDATE') and
            not has_table_privilege('anon', format('public.%I', relname), 'DELETE')
          ) from (values ${tables.map((name) => `('${name}')`).join(',')}) as t(relname)
        ),
        'profile_minimum',
          has_table_privilege('authenticated','public.users','SELECT') and
          has_column_privilege('authenticated','public.users','username','UPDATE') and
          has_column_privilege('authenticated','public.users','display_name','UPDATE') and
          has_column_privilege('authenticated','public.users','bio','UPDATE') and
          has_column_privilege('authenticated','public.users','avatar_url','UPDATE') and
          has_column_privilege('authenticated','public.users','header_url','UPDATE') and
          not has_column_privilege('authenticated','public.users','id','UPDATE') and
          not has_column_privilege('authenticated','public.users','created_at','UPDATE') and
          not has_column_privilege('authenticated','public.users','updated_at','UPDATE') and
          not has_table_privilege('authenticated','public.users','INSERT') and
          not has_table_privilege('authenticated','public.users','DELETE'),
        'posts_minimum',
          has_table_privilege('authenticated','public.posts','SELECT') and
          has_column_privilege('authenticated','public.posts','id','INSERT') and
          has_column_privilege('authenticated','public.posts','author_id','INSERT') and
          has_column_privilege('authenticated','public.posts','body','INSERT') and
          has_column_privilege('authenticated','public.posts','reply_to_post_id','INSERT') and
          has_column_privilege('authenticated','public.posts','repost_of_post_id','INSERT') and
          not has_column_privilege('authenticated','public.posts','deleted_at','INSERT') and
          not has_table_privilege('authenticated','public.posts','UPDATE') and
          not has_table_privilege('authenticated','public.posts','DELETE'),
        'children_minimum',
          has_table_privilege('authenticated','public.post_media','SELECT') and
          has_table_privilege('authenticated','public.post_media','DELETE') and
          has_column_privilege('authenticated','public.post_media','post_id','INSERT') and
          has_column_privilege('authenticated','public.post_media','url','UPDATE') and
          has_table_privilege('authenticated','public.likes','SELECT') and
          has_table_privilege('authenticated','public.likes','DELETE') and
          has_column_privilege('authenticated','public.likes','user_id','INSERT') and
          has_table_privilege('authenticated','public.post_hashtags','SELECT') and
          has_table_privilege('authenticated','public.post_hashtags','INSERT') and
          has_table_privilege('authenticated','public.post_hashtags','DELETE') and
          has_table_privilege('authenticated','public.bookmarks','SELECT') and
          has_table_privilege('authenticated','public.bookmarks','DELETE') and
          has_column_privilege('authenticated','public.bookmarks','user_id','INSERT'),
        'follow_hashtag_minimum',
          has_table_privilege('authenticated','public.follows','SELECT') and
          has_table_privilege('authenticated','public.follows','DELETE') and
          has_column_privilege('authenticated','public.follows','follower_id','INSERT') and
          has_table_privilege('authenticated','public.hashtags','SELECT') and
          has_column_privilege('authenticated','public.hashtags','id','INSERT') and
          has_column_privilege('authenticated','public.hashtags','tag','INSERT'),
        'notification_minimum',
          has_table_privilege('authenticated','public.notifications','SELECT') and
          has_column_privilege('authenticated','public.notifications','read_at','UPDATE') and
          not has_column_privilege('authenticated','public.notifications','actor_id','UPDATE') and
          not has_column_privilege('authenticated','public.notifications','recipient_id','UPDATE') and
          not has_table_privilege('authenticated','public.notifications','INSERT') and
          not has_table_privilege('authenticated','public.notifications','DELETE'),
        'rpc_minimum',
          has_function_privilege('authenticated','public.soft_delete_post(uuid)','EXECUTE') and
          not has_function_privilege('anon','public.soft_delete_post(uuid)','EXECUTE'),
        'profile_trigger', exists(
          select 1 from pg_trigger where tgname='on_auth_user_created' and not tgisinternal
        ),
        'unneeded_parent_helper_absent', not exists(
          select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
          where n.nspname='private' and p.proname='authenticated_user_can_target_active_post'
        )
      ) as value
    ), policies as (
      select coalesce(jsonb_agg(jsonb_build_object(
        'table', tablename, 'name', policyname, 'permissive', permissive,
        'roles', roles, 'command', cmd, 'using', qual, 'check', with_check
      ) order by tablename, policyname), '[]'::jsonb) as value
      from pg_policies where schemaname='public' and tablename in (${tableList})
    ), table_catalog as (
      select jsonb_agg(jsonb_build_object(
        'table', c.relname, 'rls', c.relrowsecurity, 'force_rls', c.relforcerowsecurity,
        'acl', c.relacl::text
      ) order by c.relname) as value
      from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where n.nspname='public' and c.relname in (${tableList}) and c.relkind='r'
    ), table_grants as (
      select coalesce(jsonb_agg(jsonb_build_object(
        'table', table_name, 'grantee', grantee, 'privilege', privilege_type,
        'grantable', is_grantable
      ) order by table_name, grantee, privilege_type), '[]'::jsonb) as value
      from information_schema.role_table_grants
      where table_schema='public' and table_name in (${tableList})
        and grantee in ('anon','authenticated')
    ), column_grants as (
      select coalesce(jsonb_agg(jsonb_build_object(
        'table', table_name, 'column', column_name, 'grantee', grantee,
        'privilege', privilege_type, 'grantable', is_grantable
      ) order by table_name, column_name, grantee, privilege_type), '[]'::jsonb) as value
      from information_schema.role_column_grants
      where table_schema='public' and table_name in (${tableList})
        and grantee in ('anon','authenticated')
    ), functions as (
      select coalesce(jsonb_agg(jsonb_build_object(
        'schema', n.nspname, 'name', p.proname,
        'arguments', pg_get_function_identity_arguments(p.oid),
        'security_definer', p.prosecdef, 'settings', p.proconfig,
        'acl', p.proacl::text,
        'anon_execute', has_function_privilege('anon',p.oid,'EXECUTE'),
        'authenticated_execute', has_function_privilege('authenticated',p.oid,'EXECUTE')
      ) order by n.nspname, p.proname, pg_get_function_identity_arguments(p.oid)), '[]'::jsonb) as value
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
      where (n.nspname='private' and p.proname in (
        'authenticated_user_can_target_active_post','handle_new_user','soft_delete_owned_post'
      )) or (n.nspname='public' and p.proname='soft_delete_post')
    ), schema_acl as (
      select jsonb_agg(jsonb_build_object(
        'schema', nspname, 'acl', nspacl::text,
        'anon_usage', has_schema_privilege('anon',oid,'USAGE'),
        'authenticated_usage', has_schema_privilege('authenticated',oid,'USAGE')
      ) order by nspname) as value
      from pg_namespace where nspname='private'
    ), type_acl as (
      select jsonb_agg(jsonb_build_object(
        'schema', n.nspname, 'name', t.typname, 'acl', t.typacl::text,
        'anon_usage', has_type_privilege('anon',t.oid,'USAGE'),
        'authenticated_usage', has_type_privilege('authenticated',t.oid,'USAGE')
      ) order by n.nspname, t.typname) as value
      from pg_type t join pg_namespace n on n.oid=t.typnamespace
      where n.nspname='public' and t.typname='notification_type'
    ), triggers as (
      select coalesce(jsonb_agg(jsonb_build_object(
        'name', tgname, 'definition', pg_get_triggerdef(oid), 'enabled', tgenabled
      ) order by tgname), '[]'::jsonb) as value
      from pg_trigger where tgname='on_auth_user_created' and not tgisinternal
    )
    select jsonb_build_object(
      'minimums', minimums.value,
      'policies', policies.value,
      'table_catalog', table_catalog.value,
      'table_grants', table_grants.value,
      'column_grants', column_grants.value,
      'functions', functions.value,
      'schema_acl', schema_acl.value,
      'type_acl', type_acl.value,
      'triggers', triggers.value
    )::text
    from minimums, policies, table_catalog, table_grants, column_grants,
      functions, schema_acl, type_acl, triggers;
  `)
  const parsed = JSON.parse(raw)
  const minimums = parsed.minimums
  const passed = minimums.nine_rls === true && minimums.authenticated_bypass === false &&
    minimums.anon_no_dml === true && minimums.profile_minimum === true && minimums.posts_minimum === true &&
    minimums.children_minimum === true && minimums.follow_hashtag_minimum === true &&
    minimums.notification_minimum === true && minimums.rpc_minimum === true &&
    minimums.profile_trigger === true && minimums.unneeded_parent_helper_absent === true
  return { hash: sha256(raw), passed }
}

function adminCount(table, predicate) {
  if (!tables.includes(table) || !/^[a-z0-9_ =':,.()\-]+$/i.test(predicate)) throw new Error('unsafe admin count')
  return Number(psql(`select count(*) from public.${table} where ${predicate};`))
}

function adminPost(postId) {
  const raw = psql(`select jsonb_build_object('exists',true,'deleted',deleted_at is not null,'body_null',body is null)::text from public.posts where id=${sqlUuid(postId)};`)
  if (!raw) return { exists: false, deleted: false, body_null: false }
  return JSON.parse(raw)
}

function rememberUuid(...values) {
  for (const value of values) rememberSensitive(assertUuid(value))
}

async function main() {
  currentStep = 'configuration'
  const supplied = JSON.parse(readFileSync(0, 'utf8'))
  const apiUrl = supplied.API_URL
  const anonKey = supplied.ANON_KEY
  rememberSensitive(apiUrl, anonKey)
  if (apiUrl !== expectedApiUrl || typeof anonKey !== 'string' || anonKey.startsWith('sb_secret_') ||
      jwtPayload(anonKey).role !== 'anon') throw new Error('dedicated legacy anon configuration required')
  if (sdkVersion !== expectedSdkVersion) throw new Error('unexpected SDK version')
  const migrations = migrationManifest()
  const authFlags = localAuthSafetyFlags()
  const authFlagsOk = authFlags.emailConfirmations === true && authFlags.anonymousSignIns === false
  record('local_auth_confirmation_on_anonymous_signin_off', authFlagsOk, {
    status: 'local_config_validated', code: null, count: 2,
    data_shape: 'email_confirmation_true_anonymous_false', db_state_ok: authFlagsOk,
  })
  if (!authFlagsOk) throw new Error('local auth safety flags changed')

  currentStep = 'dedicated_stack_and_catalog'
  const running = run('docker', ['ps', '--format', '{{.Names}}']).split('\n').filter(Boolean)
  const required = ['db', 'kong', 'inbucket'].map((part) => `supabase_${part}_sns-trio-local`)
  if (!required.every((name) => running.includes(name))) throw new Error('dedicated containers missing')
  for (const name of required) {
    const bindings = JSON.parse(run('docker', ['inspect', '--format', '{{json .HostConfig.PortBindings}}', name])) ?? {}
    const entries = Object.values(bindings).flat()
    if (entries.length === 0 || entries.some((entry) => entry?.HostIp !== '127.0.0.1')) {
      throw new Error('container binding escaped loopback')
    }
  }
  const catalogBefore = catalogSnapshot()
  record('catalog_nine_rls_and_privilege_minimums', catalogBefore.passed, {
    status: 'admin_query_success', code: null, count: 9, data_shape: 'catalog_hash', db_state_ok: catalogBefore.passed,
  })
  if (!catalogBefore.passed) throw new Error('catalog contract mismatch')

  currentStep = 'ordinary_users'
  const owner = await createConfirmedUser(apiUrl, anonKey, 'owner')
  const other = await createConfirmedUser(apiUrl, anonKey, 'other')
  const anon = makeClient(apiUrl, anonKey)

  currentStep = 'anon_select_denials'
  for (const table of tables) {
    const response = await anon.from(table).select('*').limit(1)
    const passed = [401, 403].includes(response.status) && response.error?.code === '42501' && response.data === null
    record(`anon_select_${table}_denied`, passed, sdkFacts(response, true))
  }

  currentStep = 'profile_rules'
  const ownProfile = await owner.client.from('users').update({ username: `owner_${randomBytes(5).toString('hex')}` })
    .eq('id', owner.userId).select('id')
  record('profile_owner_update_one', expected(ownProfile, { status: 200, shape: 'array_1' }), sdkFacts(ownProfile, true))
  const otherProfile = await owner.client.from('users').update({ bio: 'forbidden other profile update' })
    .eq('id', other.userId).select('id')
  const otherProfileDbOk = psql(`select bio is null from public.users where id=${sqlUuid(other.userId)};`) === 't'
  record('profile_other_update_zero', expected(otherProfile, { status: 200, shape: 'array_0' }) && otherProfileDbOk,
    sdkFacts(otherProfile, otherProfileDbOk))
  const forbiddenProfileId = await owner.client.from('users').update({ id: other.userId })
    .eq('id', owner.userId).select('id')
  const profileIdsOk = psql(`select count(*) from public.users where id in (${sqlUuid(owner.userId)},${sqlUuid(other.userId)});`) === '2'
  record('profile_id_update_forbidden', expected(forbiddenProfileId, { status: 403, code: '42501', shape: 'null' }) && profileIdsOk,
    sdkFacts(forbiddenProfileId, profileIdsOk))

  currentStep = 'hashtags_and_posts'
  const hashtagOne = randomUUID()
  const hashtagTwo = randomUUID()
  const targetPost = randomUUID()
  const nullBodyPost = randomUUID()
  const replyPost = randomUUID()
  const repostPost = randomUUID()
  rememberUuid(hashtagOne, hashtagTwo, targetPost, nullBodyPost, replyPost, repostPost)
  const hashtagsInsert = await owner.client.from('hashtags').insert([
    { id: hashtagOne, tag: `normal-${randomBytes(5).toString('hex')}` },
    { id: hashtagTwo, tag: `normal-${randomBytes(5).toString('hex')}` },
  ]).select('id')
  record('hashtags_authenticated_insert_normal', expected(hashtagsInsert, { status: 201, shape: 'array_2' }), sdkFacts(hashtagsInsert, true))
  const hashtagsVisible = await other.client.from('hashtags').select('id').in('id', [hashtagOne, hashtagTwo])
  record('hashtags_authenticated_select_normal', expected(hashtagsVisible, { status: 200, shape: 'array_2' }), sdkFacts(hashtagsVisible, true))

  const targetInsert = await owner.client.from('posts').insert({ id: targetPost, author_id: owner.userId, body: 'target active post' }).select('id')
  const targetDbOk = adminPost(targetPost).exists
  record('posts_owner_insert', expected(targetInsert, { status: 201, shape: 'array_1' }) && targetDbOk, sdkFacts(targetInsert, targetDbOk))
  const nullInsert = await owner.client.from('posts').insert({ id: nullBodyPost, author_id: owner.userId, body: null }).select('id')
  const nullDbOk = adminPost(nullBodyPost).body_null
  record('posts_null_body_allowed', expected(nullInsert, { status: 201, shape: 'array_1' }) && nullDbOk, sdkFacts(nullInsert, nullDbOk))
  const forgedPostId = randomUUID()
  rememberUuid(forgedPostId)
  const forgedPost = await owner.client.from('posts').insert({ id: forgedPostId, author_id: other.userId, body: 'forged' }).select('id')
  const forgedPostDbOk = adminCount('posts', `id=${sqlUuid(forgedPostId)}`) === 0
  record('posts_forged_author_denied', expected(forgedPost, { status: 403, code: '42501', shape: 'null' }) && forgedPostDbOk,
    sdkFacts(forgedPost, forgedPostDbOk))
  const replyInsert = await owner.client.from('posts').insert({ id: replyPost, author_id: owner.userId, body: 'reply', reply_to_post_id: targetPost }).select('id')
  record('posts_active_reply_allowed', expected(replyInsert, { status: 201, shape: 'array_1' }), sdkFacts(replyInsert, adminPost(replyPost).exists))
  const repostInsert = await owner.client.from('posts').insert({ id: repostPost, author_id: owner.userId, body: null, repost_of_post_id: targetPost }).select('id')
  record('posts_active_repost_allowed', expected(repostInsert, { status: 201, shape: 'array_1' }), sdkFacts(repostInsert, adminPost(repostPost).exists))
  const arbitraryUpdate = await owner.client.from('posts').update({ body: 'arbitrary update' }).eq('id', targetPost).select('id')
  const updateDbOk = adminPost(targetPost).exists && !adminPost(targetPost).deleted &&
    psql(`select body='target active post' from public.posts where id=${sqlUuid(targetPost)};`) === 't'
  record('posts_arbitrary_update_privilege_denied', expected(arbitraryUpdate, { status: 403, code: '42501', shape: 'null' }) && updateDbOk,
    sdkFacts(arbitraryUpdate, updateDbOk))
  const arbitraryDelete = await owner.client.from('posts').delete().eq('id', targetPost).select('id')
  const deleteDbOk = adminPost(targetPost).exists && !adminPost(targetPost).deleted
  record('posts_physical_delete_privilege_denied', expected(arbitraryDelete, { status: 403, code: '42501', shape: 'null' }) && deleteDbOk,
    sdkFacts(arbitraryDelete, deleteDbOk))

  currentStep = 'active_parent_children'
  const mediaId = randomUUID()
  rememberUuid(mediaId)
  const mediaInsert = await owner.client.from('post_media').insert({ id: mediaId, post_id: targetPost, url: 'https://example.test/media', order: 0 }).select('id')
  record('media_owner_active_insert', expected(mediaInsert, { status: 201, shape: 'array_1' }), sdkFacts(mediaInsert, adminCount('post_media', `id=${sqlUuid(mediaId)}`) === 1))
  const mediaOtherUpdate = await other.client.from('post_media').update({ url: 'https://example.test/forbidden' }).eq('id', mediaId).select('id')
  const mediaOtherUpdateDbOk = psql(`select url='https://example.test/media' from public.post_media where id=${sqlUuid(mediaId)};`) === 't'
  record('media_other_update_zero', expected(mediaOtherUpdate, { status: 200, shape: 'array_0' }) && mediaOtherUpdateDbOk,
    sdkFacts(mediaOtherUpdate, mediaOtherUpdateDbOk))
  const mediaOtherDelete = await other.client.from('post_media').delete().eq('id', mediaId).select('id')
  record('media_other_delete_zero', expected(mediaOtherDelete, { status: 200, shape: 'array_0' }), sdkFacts(mediaOtherDelete, adminCount('post_media', `id=${sqlUuid(mediaId)}`) === 1))

  const forgedLike = await owner.client.from('likes').insert({ user_id: other.userId, post_id: targetPost, created_at: new Date().toISOString() }).select('post_id')
  const forgedLikeDbOk = adminCount('likes', `user_id=${sqlUuid(other.userId)} and post_id=${sqlUuid(targetPost)}`) === 0
  record('likes_forged_user_denied', expected(forgedLike, { status: 403, code: '42501', shape: 'null' }) && forgedLikeDbOk,
    sdkFacts(forgedLike, forgedLikeDbOk))
  const likeInsert = await other.client.from('likes').insert({ user_id: other.userId, post_id: targetPost, created_at: new Date().toISOString() }).select('post_id')
  record('likes_owner_active_insert', expected(likeInsert, { status: 201, shape: 'array_1' }), sdkFacts(likeInsert, adminCount('likes', `user_id=${sqlUuid(other.userId)} and post_id=${sqlUuid(targetPost)}`) === 1))
  const likeOtherDelete = await owner.client.from('likes').delete().eq('user_id', other.userId).eq('post_id', targetPost).select('post_id')
  record('likes_other_delete_zero', expected(likeOtherDelete, { status: 200, shape: 'array_0' }), sdkFacts(likeOtherDelete, true))

  const postHashtagInsert = await owner.client.from('post_hashtags').insert({ post_id: targetPost, hashtag_id: hashtagOne }).select('post_id')
  record('post_hashtags_post_owner_insert', expected(postHashtagInsert, { status: 201, shape: 'array_1' }), sdkFacts(postHashtagInsert, true))
  const postHashtagOtherDelete = await other.client.from('post_hashtags').delete().eq('post_id', targetPost).eq('hashtag_id', hashtagOne).select('post_id')
  const postHashtagOtherDeleteDbOk = adminCount('post_hashtags', `post_id=${sqlUuid(targetPost)} and hashtag_id=${sqlUuid(hashtagOne)}`) === 1
  record('post_hashtags_other_delete_zero', expected(postHashtagOtherDelete, { status: 200, shape: 'array_0' }) && postHashtagOtherDeleteDbOk,
    sdkFacts(postHashtagOtherDelete, postHashtagOtherDeleteDbOk))

  const forgedBookmark = await owner.client.from('bookmarks').insert({ user_id: other.userId, post_id: targetPost, created_at: new Date().toISOString() }).select('post_id')
  const forgedBookmarkDbOk = adminCount('bookmarks', `user_id=${sqlUuid(other.userId)} and post_id=${sqlUuid(targetPost)}`) === 0
  record('bookmarks_forged_user_denied', expected(forgedBookmark, { status: 403, code: '42501', shape: 'null' }) && forgedBookmarkDbOk,
    sdkFacts(forgedBookmark, forgedBookmarkDbOk))
  const bookmarkInsert = await other.client.from('bookmarks').insert({ user_id: other.userId, post_id: targetPost, created_at: new Date().toISOString() }).select('post_id')
  record('bookmarks_owner_active_insert', expected(bookmarkInsert, { status: 201, shape: 'array_1' }), sdkFacts(bookmarkInsert, true))
  const bookmarkOtherDelete = await owner.client.from('bookmarks').delete().eq('user_id', other.userId).eq('post_id', targetPost).select('post_id')
  const bookmarkOtherDeleteDbOk = adminCount('bookmarks', `user_id=${sqlUuid(other.userId)} and post_id=${sqlUuid(targetPost)}`) === 1
  record('bookmarks_other_delete_zero', expected(bookmarkOtherDelete, { status: 200, shape: 'array_0' }) && bookmarkOtherDeleteDbOk,
    sdkFacts(bookmarkOtherDelete, bookmarkOtherDeleteDbOk))

  currentStep = 'follows'
  const forgedFollow = await owner.client.from('follows').insert({ follower_id: other.userId, followee_id: owner.userId, created_at: new Date().toISOString() }).select('follower_id')
  const forgedFollowDbOk = adminCount('follows', `follower_id=${sqlUuid(other.userId)} and followee_id=${sqlUuid(owner.userId)}`) === 0
  record('follows_forged_follower_denied', expected(forgedFollow, { status: 403, code: '42501', shape: 'null' }) && forgedFollowDbOk,
    sdkFacts(forgedFollow, forgedFollowDbOk))
  const followInsert = await other.client.from('follows').insert({ follower_id: other.userId, followee_id: owner.userId, created_at: new Date().toISOString() }).select('follower_id')
  record('follows_owner_insert', expected(followInsert, { status: 201, shape: 'array_1' }), sdkFacts(followInsert, true))
  const followOtherDelete = await owner.client.from('follows').delete().eq('follower_id', other.userId).eq('followee_id', owner.userId).select('follower_id')
  record('follows_other_delete_zero', expected(followOtherDelete, { status: 200, shape: 'array_0' }), sdkFacts(followOtherDelete, adminCount('follows', `follower_id=${sqlUuid(other.userId)} and followee_id=${sqlUuid(owner.userId)}`) === 1))

  currentStep = 'notifications_admin_seed'
  const postNotification = randomUUID()
  const followNotification = randomUUID()
  const blockedNotification = randomUUID()
  rememberUuid(postNotification, followNotification, blockedNotification)
  const seededAt = assertTimestamp(new Date().toISOString())
  psql(`
    insert into public.notifications(id,recipient_id,actor_id,type,post_id,created_at) values
      (${sqlUuid(postNotification)},${sqlUuid(other.userId)},${sqlUuid(owner.userId)},'like',${sqlUuid(targetPost)},'${seededAt}'::timestamptz),
      (${sqlUuid(followNotification)},${sqlUuid(other.userId)},${sqlUuid(owner.userId)},'follow',null,'${seededAt}'::timestamptz);
  `)
  const notificationSeedOk = adminCount('notifications', `id in (${sqlUuid(postNotification)},${sqlUuid(followNotification)})`) === 2
  record('notifications_admin_seed_only', notificationSeedOk, {
    status: 'admin_insert_success', code: null, count: 2, data_shape: 'admin_rows_2', db_state_ok: notificationSeedOk,
  })
  const recipientSelect = await other.client.from('notifications').select('id').in('id', [postNotification, followNotification])
  record('notifications_recipient_select_two', expected(recipientSelect, { status: 200, shape: 'array_2' }), sdkFacts(recipientSelect, notificationSeedOk))
  const otherSelect = await owner.client.from('notifications').select('id').in('id', [postNotification, followNotification])
  record('notifications_other_select_zero', expected(otherSelect, { status: 200, shape: 'array_0' }), sdkFacts(otherSelect, notificationSeedOk))
  const otherReadUpdate = await owner.client.from('notifications').update({ read_at: new Date().toISOString() }).eq('id', followNotification).select('id')
  const otherReadDbOk = psql(`select read_at is null from public.notifications where id=${sqlUuid(followNotification)};`) === 't'
  record('notifications_other_read_update_zero', expected(otherReadUpdate, { status: 200, shape: 'array_0' }) && otherReadDbOk,
    sdkFacts(otherReadUpdate, otherReadDbOk))
  const ownReadUpdate = await other.client.from('notifications').update({ read_at: new Date().toISOString() }).eq('id', postNotification).select('id')
  const ownReadDbOk = psql(`select read_at is not null from public.notifications where id=${sqlUuid(postNotification)};`) === 't'
  record('notifications_recipient_read_at_update_one', expected(ownReadUpdate, { status: 200, shape: 'array_1' }) && ownReadDbOk, sdkFacts(ownReadUpdate, ownReadDbOk))
  const forbiddenNotificationUpdate = await other.client.from('notifications').update({ actor_id: other.userId }).eq('id', followNotification).select('id')
  const notificationActorDbOk = psql(`select actor_id=${sqlUuid(owner.userId)} from public.notifications where id=${sqlUuid(followNotification)};`) === 't'
  record('notifications_non_read_column_update_denied', expected(forbiddenNotificationUpdate, { status: 403, code: '42501', shape: 'null' }) && notificationActorDbOk,
    sdkFacts(forbiddenNotificationUpdate, notificationActorDbOk))
  const revokedNotificationInsert = await other.client.from('notifications').insert({
    id: blockedNotification, recipient_id: other.userId, actor_id: owner.userId, type: 'follow', post_id: null, created_at: new Date().toISOString(),
  }).select('id')
  const blockedNotificationDbOk = adminCount('notifications', `id=${sqlUuid(blockedNotification)}`) === 0
  record('notifications_client_insert_revoked', expected(revokedNotificationInsert, { status: 403, code: '42501', shape: 'null' }) && blockedNotificationDbOk,
    sdkFacts(revokedNotificationInsert, blockedNotificationDbOk))

  currentStep = 'soft_delete_rpc'
  const otherSoftDelete = await other.client.rpc('soft_delete_post', { p_post_id: targetPost })
  const afterOtherDelete = adminPost(targetPost)
  record('soft_delete_rpc_other_false', expected(otherSoftDelete, { status: 200, shape: 'boolean_false' }) && !afterOtherDelete.deleted,
    sdkFacts(otherSoftDelete, !afterOtherDelete.deleted))
  const ownerSoftDelete = await owner.client.rpc('soft_delete_post', { p_post_id: targetPost })
  const afterOwnerDelete = adminPost(targetPost)
  record('soft_delete_rpc_owner_true', expected(ownerSoftDelete, { status: 200, shape: 'boolean_true' }) && afterOwnerDelete.deleted,
    sdkFacts(ownerSoftDelete, afterOwnerDelete.deleted))
  const repeatSoftDelete = await owner.client.rpc('soft_delete_post', { p_post_id: targetPost })
  record('soft_delete_rpc_repeat_false', expected(repeatSoftDelete, { status: 200, shape: 'boolean_false' }) && adminPost(targetPost).deleted,
    sdkFacts(repeatSoftDelete, adminPost(targetPost).deleted))
  const physicalPostOk = adminCount('posts', `id=${sqlUuid(targetPost)}`) === 1
  record('soft_deleted_post_physically_preserved', physicalPostOk, {
    status: 'admin_query_success', code: null, count: 1, data_shape: 'physical_row_1', db_state_ok: physicalPostOk,
  })

  currentStep = 'dead_parent_inserts'
  const deadReply = randomUUID()
  const deadRepost = randomUUID()
  const deadMedia = randomUUID()
  rememberUuid(deadReply, deadRepost, deadMedia)
  const deadReplyInsert = await owner.client.from('posts').insert({ id: deadReply, author_id: owner.userId, body: 'dead reply', reply_to_post_id: targetPost }).select('id')
  const deadReplyDbOk = adminCount('posts', `id=${sqlUuid(deadReply)}`) === 0
  record('posts_dead_reply_denied', expected(deadReplyInsert, { status: 403, code: '42501', shape: 'null' }) && deadReplyDbOk,
    sdkFacts(deadReplyInsert, deadReplyDbOk))
  const deadRepostInsert = await owner.client.from('posts').insert({ id: deadRepost, author_id: owner.userId, body: null, repost_of_post_id: targetPost }).select('id')
  const deadRepostDbOk = adminCount('posts', `id=${sqlUuid(deadRepost)}`) === 0
  record('posts_dead_repost_denied', expected(deadRepostInsert, { status: 403, code: '42501', shape: 'null' }) && deadRepostDbOk,
    sdkFacts(deadRepostInsert, deadRepostDbOk))
  const deadMediaInsert = await owner.client.from('post_media').insert({ id: deadMedia, post_id: targetPost, url: 'https://example.test/dead', order: 1 }).select('id')
  const deadMediaDbOk = adminCount('post_media', `id=${sqlUuid(deadMedia)}`) === 0
  record('media_dead_parent_insert_denied', expected(deadMediaInsert, { status: 403, code: '42501', shape: 'null' }) && deadMediaDbOk,
    sdkFacts(deadMediaInsert, deadMediaDbOk))
  const deadLikeInsert = await owner.client.from('likes').insert({ user_id: owner.userId, post_id: targetPost, created_at: new Date().toISOString() }).select('post_id')
  const deadLikeDbOk = adminCount('likes', `user_id=${sqlUuid(owner.userId)} and post_id=${sqlUuid(targetPost)}`) === 0
  record('likes_dead_parent_insert_denied', expected(deadLikeInsert, { status: 403, code: '42501', shape: 'null' }) && deadLikeDbOk,
    sdkFacts(deadLikeInsert, deadLikeDbOk))
  const deadPostHashtagInsert = await owner.client.from('post_hashtags').insert({ post_id: targetPost, hashtag_id: hashtagTwo }).select('post_id')
  const deadPostHashtagDbOk = adminCount('post_hashtags', `post_id=${sqlUuid(targetPost)} and hashtag_id=${sqlUuid(hashtagTwo)}`) === 0
  record('post_hashtags_dead_parent_insert_denied', expected(deadPostHashtagInsert, { status: 403, code: '42501', shape: 'null' }) && deadPostHashtagDbOk,
    sdkFacts(deadPostHashtagInsert, deadPostHashtagDbOk))
  const deadBookmarkInsert = await owner.client.from('bookmarks').insert({ user_id: owner.userId, post_id: targetPost, created_at: new Date().toISOString() }).select('post_id')
  const deadBookmarkDbOk = adminCount('bookmarks', `user_id=${sqlUuid(owner.userId)} and post_id=${sqlUuid(targetPost)}`) === 0
  record('bookmarks_dead_parent_insert_denied', expected(deadBookmarkInsert, { status: 403, code: '42501', shape: 'null' }) && deadBookmarkDbOk,
    sdkFacts(deadBookmarkInsert, deadBookmarkDbOk))

  currentStep = 'hidden_children_preserved'
  const hiddenCases = [
    ['post_media', owner.client.from('post_media').select('id').eq('id', mediaId), `id=${sqlUuid(mediaId)}`],
    ['likes', other.client.from('likes').select('post_id').eq('user_id', other.userId).eq('post_id', targetPost), `user_id=${sqlUuid(other.userId)} and post_id=${sqlUuid(targetPost)}`],
    ['post_hashtags', owner.client.from('post_hashtags').select('post_id').eq('post_id', targetPost).eq('hashtag_id', hashtagOne), `post_id=${sqlUuid(targetPost)} and hashtag_id=${sqlUuid(hashtagOne)}`],
    ['bookmarks', other.client.from('bookmarks').select('post_id').eq('user_id', other.userId).eq('post_id', targetPost), `user_id=${sqlUuid(other.userId)} and post_id=${sqlUuid(targetPost)}`],
  ]
  for (const [table, promise, predicate] of hiddenCases) {
    const response = await promise
    const adminPreserved = adminCount(table, predicate) === 1
    record(`${table}_hidden_after_parent_delete_admin_preserved`, expected(response, { status: 200, shape: 'array_0' }) && adminPreserved,
      sdkFacts(response, adminPreserved))
  }
  const deletedLike = await other.client.from('likes').delete().eq('user_id', other.userId).eq('post_id', targetPost).select('post_id')
  const deletedLikePreserved = adminCount('likes', `user_id=${sqlUuid(other.userId)} and post_id=${sqlUuid(targetPost)}`) === 1
  record('likes_owner_delete_after_parent_deleted_zero_preserved',
    expected(deletedLike, { status: 200, shape: 'array_0' }) && deletedLikePreserved,
    sdkFacts(deletedLike, deletedLikePreserved))
  const deletedBookmark = await other.client.from('bookmarks').delete().eq('user_id', other.userId).eq('post_id', targetPost).select('post_id')
  const deletedBookmarkPreserved = adminCount('bookmarks', `user_id=${sqlUuid(other.userId)} and post_id=${sqlUuid(targetPost)}`) === 1
  record('bookmarks_owner_delete_after_parent_deleted_zero_preserved',
    expected(deletedBookmark, { status: 200, shape: 'array_0' }) && deletedBookmarkPreserved,
    sdkFacts(deletedBookmark, deletedBookmarkPreserved))
  const hashtagStillVisible = await other.client.from('hashtags').select('id').eq('id', hashtagOne)
  record('hashtags_remain_visible_after_post_delete', expected(hashtagStillVisible, { status: 200, shape: 'array_1' }), sdkFacts(hashtagStillVisible, true))
  const notificationsAfterDelete = await other.client.from('notifications').select('id').in('id', [postNotification, followNotification])
  const notificationRowsPreserved = adminCount('notifications', `id in (${sqlUuid(postNotification)},${sqlUuid(followNotification)})`) === 2
  const exactFollowVisible = notificationsAfterDelete.data?.length === 1 && notificationsAfterDelete.data[0]?.id === followNotification
  record('notifications_post_hidden_follow_visible_after_delete', expected(notificationsAfterDelete, { status: 200, shape: 'array_1' }) && exactFollowVisible && notificationRowsPreserved,
    sdkFacts(notificationsAfterDelete, notificationRowsPreserved))
  const readAtBeforeHiddenUpdate = psql(`select coalesce(read_at::text,'NULL') from public.notifications where id=${sqlUuid(postNotification)};`)
  const hiddenNotificationUpdate = await other.client.from('notifications')
    .update({ read_at: new Date(Date.now() + 60_000).toISOString() })
    .eq('id', postNotification)
    .select('id')
  const readAtAfterHiddenUpdate = psql(`select coalesce(read_at::text,'NULL') from public.notifications where id=${sqlUuid(postNotification)};`)
  const hiddenNotificationDbUnchanged = readAtBeforeHiddenUpdate === readAtAfterHiddenUpdate
  record('notifications_hidden_post_read_update_zero_unchanged',
    expected(hiddenNotificationUpdate, { status: 200, shape: 'array_0' }) && hiddenNotificationDbUnchanged,
    sdkFacts(hiddenNotificationUpdate, hiddenNotificationDbUnchanged))

  const noFilterNotificationUpdate = await other.client.from('notifications')
    .update({ read_at: new Date(Date.now() + 120_000).toISOString() })
  const readAtAfterNoFilterUpdate = psql(`select coalesce(read_at::text,'NULL') from public.notifications where id=${sqlUuid(postNotification)};`)
  const noFilterHiddenUnchanged = readAtAfterNoFilterUpdate === readAtAfterHiddenUpdate
  record('notifications_no_filter_no_returning_hidden_unchanged', noFilterHiddenUnchanged,
    sdkFacts(noFilterNotificationUpdate, noFilterHiddenUnchanged))

  currentStep = 'catalog_after'
  const catalogAfter = catalogSnapshot()
  const catalogStable = catalogAfter.passed && catalogBefore.hash === catalogAfter.hash
  record('catalog_unchanged_after_measurement', catalogStable, {
    status: 'admin_query_success', code: null, count: 9, data_shape: 'catalog_hash_pair', db_state_ok: catalogStable,
  })

  return {
    scope: 'NON_FORMAL_D4_PREDECESSOR_SDK_CANDIDATE',
    statement_scope: 'Pinned Supabase-JS RLS behavior for the frozen nine-table candidate only; not formal full DB13, D4, or G6 acceptance',
    started_at_utc: startedAtUtc,
    completed_at_utc: new Date().toISOString(),
    elapsed_seconds: Number(((performance.now() - startedMonotonic) / 1000).toFixed(3)),
    sdk: { package: '@supabase/supabase-js', version: sdkVersion },
    source_sha256: {
      migrations,
      measure_sdk: sha256(readFileSync(fileURLToPath(import.meta.url))),
    },
    catalog_sha256: { before: catalogBefore.hash, after: catalogAfter.hash },
    checks,
    all_measured_checks_pass: checks.every((check) => check.passed),
    not_measured: [
      'concurrent_writes_or_races',
      'full_DB13_matrix',
      'D4_authoring_effort',
      'G6_execution',
      'hosted_project',
      'external_email_delivery',
      'Realtime',
      'Storage',
      'formal_B27_U19_U20_decisions',
    ],
  }
}

try {
  const outputPath = parseArguments(process.argv.slice(2))
  outputFd = openSync(outputPath, 'wx', 0o600)
  let report
  try {
    report = await main()
  } finally {
    await cleanupLocalSessions()
  }
  report.cleanup = cleanup
  report.all_measured_checks_pass = report.all_measured_checks_pass && cleanup.failed === 0
  writeFileSync(outputFd, serializeReport(report))
  closeSync(outputFd)
  outputFd = undefined
  const passed = report.checks.filter((check) => check.passed).length
  process.stdout.write(`${JSON.stringify({ checks: report.checks.length, passed, failed: report.checks.length - passed })}\n`)
  process.exitCode = report.all_measured_checks_pass ? 0 : 2
} catch (error) {
  const failureReport = {
    scope: 'NON_FORMAL_D4_PREDECESSOR_SDK_CANDIDATE',
    statement_scope: 'Pinned Supabase-JS RLS behavior for the frozen nine-table candidate only; not formal full DB13, D4, or G6 acceptance',
    started_at_utc: startedAtUtc,
    completed_at_utc: new Date().toISOString(),
    elapsed_seconds: Number(((performance.now() - startedMonotonic) / 1000).toFixed(3)),
    sdk: { package: '@supabase/supabase-js', version: sdkVersion },
    failure: { step: currentStep, kind: fixedFailureKind(error) },
    cleanup,
    checks,
    all_measured_checks_pass: false,
  }
  if (outputFd !== undefined) {
    try {
      writeFileSync(outputFd, serializeReport(failureReport))
    } catch {
      writeFileSync(outputFd, `${JSON.stringify({
        scope: 'NON_FORMAL_D4_PREDECESSOR_SDK_CANDIDATE',
        failure: { step: 'redaction_guard', kind: 'redaction_guard_rejected_report' },
        cleanup,
        all_measured_checks_pass: false,
      }, null, 2)}\n`)
    }
    closeSync(outputFd)
  }
  process.stdout.write(`${JSON.stringify({ checks: checks.length, passed: checks.filter((check) => check.passed).length, failed: true })}\n`)
  process.exitCode = 2
}
