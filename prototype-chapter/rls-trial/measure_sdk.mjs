#!/usr/bin/env node
/**
 * Measure the M1 RLS result-shape matrix with the pinned Supabase JavaScript SDK.
 *
 * The dedicated CLI status JSON is read only from stdin. Secrets, synthetic user
 * identifiers, row identifiers, tokens, URLs, and credentials never enter the
 * report. Administrative verification is sent to psql over stdin rather than
 * command-line arguments.
 */
import { createHash, randomBytes } from 'node:crypto'
import { closeSync, openSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { performance } from 'node:perf_hooks'
import { spawnSync } from 'node:child_process'

const require = createRequire(new URL('../candidates/auth-sdk57/package.json', import.meta.url))
const { createClient } = require('@supabase/supabase-js')
const sdkVersion = require('@supabase/supabase-js/package.json').version

const here = dirname(fileURLToPath(import.meta.url))
const databaseContainer = 'supabase_db_sns-trio-local'
const expectedApiUrl = 'http://127.0.0.1:54321'
const mailpitUrl = 'http://127.0.0.1:54324'
const expectedSdkVersion = '2.117.2'

let currentStep = 'argument_validation'
let outputFd
let outputPath
let checks = []
const createdClients = []
const sensitiveValues = new Set()
const cleanupStatus = {
  scope: 'local_client_session_only',
  attempted: 0,
  succeeded: 0,
  failed: 0,
  access_jwt_revocation_measured: false,
}
const startedAtUtc = new Date().toISOString()
const startedMonotonic = performance.now()

function sha256Bytes(value) {
  return createHash('sha256').update(value).digest('hex')
}

function fixedFailureKind(error) {
  if (error instanceof SyntaxError) return 'invalid_json'
  if (error instanceof TypeError) return 'type_error'
  if (error && typeof error === 'object' && error.name === 'AbortError') return 'timeout'
  return 'measurement_error'
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

function jwtPayload(token) {
  if (typeof token !== 'string' || token.startsWith('sb_secret_')) {
    throw new Error('legacy JWT required')
  }
  const parts = token.split('.')
  if (parts.length !== 3) throw new Error('legacy JWT required')
  const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'))
  if (!payload || typeof payload !== 'object') throw new Error('invalid JWT payload')
  return payload
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

async function cleanupLocalSessions() {
  cleanupStatus.attempted = createdClients.length
  for (const client of createdClients) {
    try {
      const result = await client.auth.signOut({ scope: 'local' })
      if (result.error) cleanupStatus.failed += 1
      else cleanupStatus.succeeded += 1
    } catch {
      cleanupStatus.failed += 1
    }
  }
}

function parseArguments(argv) {
  if (argv.length !== 2 || argv[0] !== '--output' || !argv[1]) {
    throw new Error('expected --output with a fresh path')
  }
  return resolve(argv[1])
}

function run(command, args, options = {}) {
  const completed = spawnSync(command, args, {
    encoding: 'utf8',
    maxBuffer: 1024 * 1024,
    ...options,
  })
  if (completed.status !== 0 || completed.error) {
    throw new Error('subprocess failed')
  }
  return completed.stdout.trim()
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
  if (typeof data === 'number' && Number.isInteger(data)) return 'integer'
  if (Array.isArray(data)) {
    if (data.length === 0) return 'array_0'
    if (data.length === 1 && data[0] && Object.keys(data[0]).length === 1 && typeof data[0].id === 'string') {
      return 'array_1_id_only'
    }
    return `array_${data.length}_other`
  }
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

function assertUuid(value) {
  if (typeof value !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) {
    throw new Error('invalid UUID from dedicated stack')
  }
  return value
}

function assertFixedBody(value) {
  if (typeof value !== 'string' || !/^m1-[a-z0-9-]{1,64}$/.test(value)) {
    throw new Error('invalid fixed body marker')
  }
  return value
}

function adminRow(postId) {
  const id = assertUuid(postId)
  const raw = psql(`
    SELECT body || E'\\t' || (deleted_at IS NOT NULL)::text || E'\\t' || author_id::text
      FROM public.trial_posts
     WHERE id = '${id}'::uuid;
  `)
  const [body, deleted, authorId] = raw.split('\t')
  return { body, deleted: deleted === 'true' || deleted === 't', authorId: assertUuid(authorId) }
}

function adminCount(sqlPredicate) {
  if (!/^[a-z0-9_ =':.()-]+$/i.test(sqlPredicate)) throw new Error('unsafe administrative predicate')
  return Number(psql(`SELECT count(*) FROM public.trial_posts WHERE ${sqlPredicate};`))
}

function installedContractSnapshot() {
  const canonical = psql(`
    WITH column_contract AS (
      SELECT jsonb_agg(jsonb_build_object(
        'name', a.attname,
        'type', format_type(a.atttypid, a.atttypmod),
        'not_null', a.attnotnull,
        'default', pg_get_expr(d.adbin, d.adrelid)
      ) ORDER BY a.attnum) AS value
      FROM pg_attribute a
      LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
      WHERE a.attrelid = 'public.trial_posts'::regclass
        AND a.attnum > 0 AND NOT a.attisdropped
    ), policy_contract AS (
      SELECT jsonb_agg(jsonb_build_object(
        'name', policyname, 'command', cmd, 'roles', roles,
        'using', qual, 'check', with_check
      ) ORDER BY policyname) AS value
      FROM pg_policies
      WHERE schemaname = 'public' AND tablename = 'trial_posts'
    ), grant_contract AS (
      SELECT jsonb_agg(jsonb_build_object(
        'grantee', grantee, 'privilege', privilege_type
      ) ORDER BY grantee, privilege_type) AS value
      FROM information_schema.role_table_grants
      WHERE table_schema = 'public' AND table_name = 'trial_posts'
        AND grantee IN ('anon', 'authenticated')
    ), function_contract AS (
      SELECT jsonb_build_object(
        'security_definer', p.prosecdef,
        'settings', p.proconfig,
        'source', p.prosrc,
        'anon_execute', has_function_privilege('anon', p.oid, 'EXECUTE'),
        'authenticated_execute', has_function_privilege('authenticated', p.oid, 'EXECUTE')
      ) AS value
      FROM pg_proc p
      WHERE p.oid = 'public.trial_soft_delete(uuid)'::regprocedure
    )
    SELECT jsonb_build_object(
      'columns', column_contract.value,
      'policies', policy_contract.value,
      'grants', grant_contract.value,
      'function', function_contract.value,
      'rls', (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.trial_posts'::regclass)
    )::text
    FROM column_contract, policy_contract, grant_contract, function_contract;
  `)
  if (!canonical) throw new Error('installed contract missing')
  return sha256Bytes(canonical)
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
      const messageId = encodeURIComponent(matches[0].ID)
      const message = await fetchJson(`${mailpitUrl}/api/v1/message/${messageId}`)
      const hrefs = [...String(message.HTML ?? '').matchAll(/href="([^"]+)"/g)]
        .map((match) => match[1].replaceAll('&amp;', '&'))
      for (const href of hrefs) {
        rememberSensitive(href)
        const candidate = new URL(href)
        if (
          candidate.origin === expectedApiUrl &&
          candidate.pathname === '/auth/v1/verify' &&
          candidate.searchParams.get('type') === 'signup' &&
          candidate.searchParams.has('token')
        ) {
          const tokenHash = candidate.searchParams.get('token')
          rememberSensitive(tokenHash)
          return tokenHash
        }
      }
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 100))
  }
  throw new Error('local confirmation message unavailable')
}

async function createConfirmedUser(apiUrl, anonKey, label) {
  const client = createClient(apiUrl, anonKey, {
    global: { fetch: boundedFetch },
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  })
  createdClients.push(client)
  const nonce = randomBytes(12).toString('hex')
  const email = `m1-${nonce}-${label}@example.test`
  const password = randomBytes(24).toString('base64url')
  rememberSensitive(email, password)
  const signup = await client.auth.signUp({ email, password })
  rememberSensitive(signup.data.user?.id)
  const signupOk = !signup.error && Boolean(signup.data.user?.id) && !signup.data.session
  record(`auth_${label}_signup_confirmation_required`, signupOk, {
    status: signup.error ? 'sdk_error' : 'sdk_success',
    code: signup.error?.code ?? null,
    count: null,
    data_shape: signup.data.session ? 'session_present' : 'session_absent',
    db_state_ok: signupOk,
  })
  if (!signupOk) throw new Error('signup setup failed')

  const tokenHash = await signupTokenHash(email)
  const verified = await client.auth.verifyOtp({ token_hash: tokenHash, type: 'signup' })
  rememberSensitive(
    verified.data.user?.id,
    verified.data.session?.access_token,
    verified.data.session?.refresh_token,
  )
  const userId = assertUuid(verified.data.user?.id)
  const sessionRole = jwtPayload(verified.data.session?.access_token).role
  const authoritative = await client.auth.getUser()
  rememberSensitive(authoritative.data.user?.id)
  const confirmationOk = !verified.error && Boolean(verified.data.session?.access_token) &&
    !authoritative.error && authoritative.data.user?.id === userId &&
    typeof authoritative.data.user?.email_confirmed_at === 'string' && sessionRole === 'authenticated'
  record(`auth_${label}_confirmed_ordinary_authenticated_role`, confirmationOk, {
    status: verified.error ? 'sdk_error' : 'sdk_success',
    code: verified.error?.code ?? authoritative.error?.code ?? null,
    count: null,
    data_shape: verified.data.session ? 'verified_authenticated_session' : 'session_absent',
    db_state_ok: confirmationOk,
  })
  if (!confirmationOk) throw new Error('confirmation setup failed')
  return { client, userId }
}

function expectedMutation(response, { status, count, shape, code = null }) {
  return response.status === status && response.count === count &&
    dataShape(response.data) === shape && (response.error?.code ?? null) === code
}

async function main() {
  currentStep = 'read_stdin_configuration'
  const supplied = JSON.parse(readFileSync(0, 'utf8'))
  const apiUrl = supplied.API_URL
  const anonKey = supplied.ANON_KEY
  rememberSensitive(apiUrl, anonKey)
  if (apiUrl !== expectedApiUrl || typeof anonKey !== 'string' || anonKey.length < 20 ||
      anonKey.startsWith('sb_secret_') || jwtPayload(anonKey).role !== 'anon') {
    throw new Error('dedicated loopback configuration required')
  }
  record('configuration_legacy_anon_role', true, {
    status: 'configuration_validated', code: null, count: 1, data_shape: 'legacy_anon_jwt', db_state_ok: true,
  })
  if (sdkVersion !== expectedSdkVersion) throw new Error('unexpected SDK version')

  currentStep = 'dedicated_stack_safety'
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
  const beforeContractHash = installedContractSnapshot()
  const authenticatedBypass = psql("SELECT rolbypassrls FROM pg_roles WHERE rolname='authenticated';")
  record('authenticated_role_does_not_bypass_rls', authenticatedBypass === 'f', {
    status: 'admin_query_success', code: null, count: 1, data_shape: 'boolean', db_state_ok: authenticatedBypass === 'f',
  })

  currentStep = 'create_confirmed_users'
  const owner = await createConfirmedUser(apiUrl, anonKey, 'owner')
  const other = await createConfirmedUser(apiUrl, anonKey, 'other')

  currentStep = 'insert_owner_row'
  const inserted = await owner.client.from('trial_posts')
    .insert({ author_id: owner.userId, body: 'm1-initial' })
    .select('id')
    .single()
  const postId = assertUuid(inserted.data?.id)
  rememberSensitive(postId)
  const initialDb = adminRow(postId)
  const initialOk = !inserted.error && inserted.status === 201 && initialDb.body === 'm1-initial' &&
    initialDb.authorId === owner.userId && !initialDb.deleted
  record('setup_owner_insert', initialOk, sdkFacts(inserted, initialOk))
  if (!initialOk) throw new Error('owner row setup failed')

  const updateVariants = [
    { name: 'default', options: {}, select: false, status: 204, count: null, ownerShape: 'null', otherShape: 'null' },
    { name: 'select_id', options: {}, select: true, status: 200, count: null, ownerShape: 'array_1_id_only', otherShape: 'array_0' },
    { name: 'count_exact', options: { count: 'exact' }, select: false, status: 204, count: 'affected', ownerShape: 'null', otherShape: 'null' },
    { name: 'count_exact_select_id', options: { count: 'exact' }, select: true, status: 200, count: 'affected', ownerShape: 'array_1_id_only', otherShape: 'array_0' },
  ]

  currentStep = 'update_shape_matrix'
  let currentBody = initialDb.body
  for (const [index, variant] of updateVariants.entries()) {
    const ownerBody = assertFixedBody(`m1-owner-${index}`)
    let ownerQuery = owner.client.from('trial_posts').update({ body: ownerBody }, variant.options).eq('id', postId)
    if (variant.select) ownerQuery = ownerQuery.select('id')
    const ownerResponse = await ownerQuery
    const ownerDb = adminRow(postId)
    const ownerCount = variant.count === 'affected' ? 1 : null
    const ownerDbOk = ownerDb.body === ownerBody && ownerDb.authorId === owner.userId && !ownerDb.deleted
    const ownerPassed = expectedMutation(ownerResponse, {
      status: variant.status, count: ownerCount, shape: variant.ownerShape,
    }) && ownerDbOk
    record(`update_owner_${variant.name}`, ownerPassed, sdkFacts(ownerResponse, ownerDbOk))
    currentBody = ownerBody

    const attemptedBody = assertFixedBody(`m1-other-${index}`)
    let otherQuery = other.client.from('trial_posts').update({ body: attemptedBody }, variant.options).eq('id', postId)
    if (variant.select) otherQuery = otherQuery.select('id')
    const otherResponse = await otherQuery
    const otherDb = adminRow(postId)
    const otherCount = variant.count === 'affected' ? 0 : null
    const otherDbOk = otherDb.body === currentBody && otherDb.authorId === owner.userId && !otherDb.deleted
    const otherPassed = expectedMutation(otherResponse, {
      status: variant.status, count: otherCount, shape: variant.otherShape,
    }) && otherDbOk
    record(`update_other_${variant.name}`, otherPassed, sdkFacts(otherResponse, otherDbOk))
  }

  const deleteVariants = [
    { name: 'default', options: {}, select: false, status: 204, count: null, shape: 'null' },
    { name: 'count_exact', options: { count: 'exact' }, select: false, status: 204, count: 0, shape: 'null' },
    { name: 'select_id', options: {}, select: true, status: 200, count: null, shape: 'array_0' },
  ]

  currentStep = 'delete_no_policy_matrix'
  for (const [actorName, actor] of [['owner', owner], ['other', other]]) {
    for (const variant of deleteVariants) {
      let query = actor.client.from('trial_posts').delete(variant.options).eq('id', postId)
      if (variant.select) query = query.select('id')
      const response = await query
      const db = adminRow(postId)
      const dbOk = db.body === currentBody && db.authorId === owner.userId && !db.deleted
      const passed = expectedMutation(response, {
        status: variant.status, count: variant.count, shape: variant.shape,
      }) && dbOk
      record(`delete_${actorName}_${variant.name}`, passed, sdkFacts(response, dbOk))
    }
  }

  currentStep = 'forged_owner_insert'
  const forged = await owner.client.from('trial_posts')
    .insert({ author_id: other.userId, body: 'm1-forged' })
    .select('id')
  const forgedCount = adminCount(`author_id = '${assertUuid(other.userId)}'::uuid AND body = 'm1-forged'`)
  const forgedDbOk = forgedCount === 0
  const forgedPassed = expectedMutation(forged, {
    status: 403, count: null, shape: 'null', code: '42501',
  }) && forgedDbOk
  record('insert_forged_author_denied', forgedPassed, sdkFacts(forged, forgedDbOk))

  currentStep = 'direct_soft_delete_matrix'
  const directVariants = [
    { name: 'minimal', options: {}, select: false },
    { name: 'count_exact', options: { count: 'exact' }, select: false },
    { name: 'select_id', options: {}, select: true },
  ]
  for (const variant of directVariants) {
    let query = owner.client.from('trial_posts')
      .update({ deleted_at: new Date().toISOString() }, variant.options)
      .eq('id', postId)
    if (variant.select) query = query.select('id')
    const response = await query
    const db = adminRow(postId)
    const dbOk = db.body === currentBody && db.authorId === owner.userId && !db.deleted
    const passed = response.status === 403 && response.error?.code === '42501' &&
      response.data === null && response.count === null && dbOk
    record(`soft_delete_direct_owner_${variant.name}_denied`, passed, sdkFacts(response, dbOk))
  }

  currentStep = 'soft_delete_rpc'
  const otherRpc = await other.client.rpc('trial_soft_delete', { target_id: postId })
  const dbAfterOtherRpc = adminRow(postId)
  const otherRpcDbOk = !dbAfterOtherRpc.deleted && dbAfterOtherRpc.body === currentBody
  const otherRpcPassed = otherRpc.status === 200 && !otherRpc.error && otherRpc.data === 0 && otherRpcDbOk
  record('soft_delete_rpc_other_zero', otherRpcPassed, sdkFacts(otherRpc, otherRpcDbOk))

  const ownerRpc = await owner.client.rpc('trial_soft_delete', { target_id: postId })
  const dbAfterOwnerRpc = adminRow(postId)
  const ownerRpcDbOk = dbAfterOwnerRpc.deleted && dbAfterOwnerRpc.body === currentBody &&
    adminCount(`id = '${assertUuid(postId)}'::uuid`) === 1
  const ownerRpcPassed = ownerRpc.status === 200 && !ownerRpc.error && ownerRpc.data === 1 && ownerRpcDbOk
  record('soft_delete_rpc_owner_one', ownerRpcPassed, sdkFacts(ownerRpc, ownerRpcDbOk))

  currentStep = 'installed_contract_after'
  const afterContractHash = installedContractSnapshot()
  const contractStable = beforeContractHash === afterContractHash
  record('installed_policy_and_schema_unchanged', contractStable, {
    status: 'admin_query_success', code: null, count: 1, data_shape: 'sha256_pair', db_state_ok: contractStable,
  })

  return {
    scope: 'NON_FORMAL_M1_CANDIDATE',
    statement_scope: 'Supabase-JS result-shape and RLS matrix only; not full DB13 or D4 acceptance',
    started_at_utc: startedAtUtc,
    completed_at_utc: new Date().toISOString(),
    elapsed_seconds: Number(((performance.now() - startedMonotonic) / 1000).toFixed(3)),
    sdk: { package: '@supabase/supabase-js', version: sdkVersion },
    installed_contract_sha256: { before: beforeContractHash, after: afterContractHash },
    source_sha256: Object.fromEntries(
      ['001_posts.sql', '002_soft_delete.sql', 'measure_sdk.mjs'].map((name) => [
        name,
        sha256Bytes(readFileSync(resolve(here, name))),
      ]),
    ),
    checks,
    all_measured_checks_pass: checks.length === 28 && checks.every((check) => check.passed),
    not_measured: [
      'full_DB13_matrix',
      'D4_authoring_effort',
      'hosted_project',
      'external_email_delivery',
      'production_migration_or_API_contract',
    ],
  }
}

try {
  outputPath = parseArguments(process.argv.slice(2))
  outputFd = openSync(outputPath, 'wx', 0o600)
  let report
  try {
    report = await main()
  } finally {
    await cleanupLocalSessions()
  }
  report.cleanup = cleanupStatus
  report.all_measured_checks_pass = report.all_measured_checks_pass && cleanupStatus.failed === 0
  writeFileSync(outputFd, serializeReport(report))
  closeSync(outputFd)
  outputFd = undefined
  const passed = report.checks.filter((check) => check.passed).length
  process.stdout.write(`${JSON.stringify({ checks: report.checks.length, passed, failed: report.checks.length - passed })}\n`)
  process.exitCode = report.all_measured_checks_pass ? 0 : 2
} catch (error) {
  const failureReport = {
    scope: 'NON_FORMAL_M1_CANDIDATE',
    statement_scope: 'Supabase-JS result-shape and RLS matrix only; not full DB13 or D4 acceptance',
    started_at_utc: startedAtUtc,
    completed_at_utc: new Date().toISOString(),
    elapsed_seconds: Number(((performance.now() - startedMonotonic) / 1000).toFixed(3)),
    sdk: { package: '@supabase/supabase-js', version: sdkVersion },
    failure: { step: currentStep, kind: fixedFailureKind(error) },
    cleanup: cleanupStatus,
    checks,
    all_measured_checks_pass: false,
  }
  if (outputFd !== undefined) {
    try {
      writeFileSync(outputFd, serializeReport(failureReport))
    } catch {
      writeFileSync(outputFd, `${JSON.stringify({
        scope: 'NON_FORMAL_M1_CANDIDATE',
        failure: { step: 'redaction_guard', kind: 'redaction_guard_rejected_report' },
        cleanup: cleanupStatus,
        all_measured_checks_pass: false,
      }, null, 2)}\n`)
    }
    closeSync(outputFd)
  }
  process.stdout.write(`${JSON.stringify({ checks: checks.length, passed: checks.filter((check) => check.passed).length, failed: true })}\n`)
  process.exitCode = 2
}
