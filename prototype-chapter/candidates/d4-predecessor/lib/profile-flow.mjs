const PROFILE_COLUMNS = 'id, username, display_name, bio';
const QUERY_TIMEOUT_MS = 15_000;

export function profilePayload(draft) {
  return {
    username: draft.username.trim() || null,
    display_name: draft.displayName.trim(),
    bio: draft.bio.trim() || null,
  };
}

export function validateProfileDraft(draft) {
  const username = draft.username.trim();
  const displayName = draft.displayName.trim();
  if (!username) return '表示IDを入力してください。';
  if (username.length > 30) return '表示IDは30文字以内で入力してください。';
  if (!displayName) return '表示名を入力してください。';
  if (displayName.length > 50) return '表示名は50文字以内で入力してください。';
  if (draft.bio.length > 160) return '自己紹介は160文字以内で入力してください。';
  return null;
}

export function createLatestRequestGuard(initialUserId) {
  let userId = initialUserId;
  let generation = 0;
  let active = true;
  return {
    begin() {
      return Object.freeze({ userId, generation: ++generation });
    },
    accepts(snapshot) {
      return active && snapshot.userId === userId && snapshot.generation === generation;
    },
    switchUser(nextUserId) {
      userId = nextUserId;
      active = true;
      generation += 1;
    },
    dispose() {
      active = false;
      generation += 1;
    },
  };
}

export function createExclusiveOperation() {
  let running = false;
  return {
    begin() {
      if (running) return false;
      running = true;
      return true;
    },
    finish() {
      running = false;
    },
  };
}

function normalizeProfile(row) {
  return {
    id: row.id,
    username: row.username ?? null,
    displayName: row.display_name ?? '',
    bio: row.bio ?? null,
  };
}

async function runQuery(builder, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await builder.abortSignal(controller.signal);
  } finally {
    clearTimeout(timer);
  }
}

function isSqlState(code) {
  return typeof code === 'string' && /^[0-9A-Z]{5}$/.test(code);
}

function profileMatches(profile, userId, payload) {
  return profile.id === userId &&
    profile.username === payload.username &&
    profile.displayName === payload.display_name &&
    profile.bio === payload.bio;
}

export function createProfileRepository(client, { timeoutMs = QUERY_TIMEOUT_MS } = {}) {
  async function read(userId) {
    let response;
    try {
      const query = client
        .from('users')
        .select(PROFILE_COLUMNS)
        .eq('id', userId)
        .maybeSingle();
      response = await runQuery(query, timeoutMs);
    } catch (error) {
      return { status: 'error', error };
    }
    if (!response || typeof response !== 'object') {
      return { status: 'error', error: new Error('Invalid profile read response') };
    }
    const { data, error } = response;
    if (error) return { status: 'error', error };
    if (!data) return { status: 'empty' };
    if (typeof data !== 'object' || data.id !== userId) {
      return { status: 'error', error: new Error('Invalid profile identity') };
    }
    return { status: 'loaded', profile: normalizeProfile(data) };
  }

  async function save(userId, draft) {
    const validationMessage = validateProfileDraft(draft);
    if (validationMessage) return { status: 'invalid', message: validationMessage };
    const payload = profilePayload(draft);
    let response;
    try {
      const query = client
        .from('users')
        .update(payload)
        .eq('id', userId)
        .select(PROFILE_COLUMNS);
      response = await runQuery(query, timeoutMs);
    } catch (error) {
      return { status: 'unconfirmed', error };
    }
    if (!response || typeof response !== 'object') {
      return { status: 'unconfirmed', error: new Error('Invalid profile update response') };
    }
    const { data, error, status } = response;
    if (error) {
      if (error.code === '23505') return { status: 'conflict' };
      if (status === 0 || !isSqlState(error.code)) return { status: 'unconfirmed', error };
      return { status: 'error', error };
    }
    if (!Array.isArray(data)) return { status: 'unconfirmed' };
    if (data.length === 0) return { status: 'zero_rows' };
    if (data.length !== 1) return { status: 'unconfirmed' };
    const reread = await read(userId);
    if (reread.status !== 'loaded' || !profileMatches(reread.profile, userId, payload)) {
      return { status: 'unconfirmed', reread };
    }
    return { status: 'saved', profile: reread.profile };
  }

  return Object.freeze({ read, save });
}
