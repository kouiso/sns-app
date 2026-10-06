import type { SupabaseClient } from '@supabase/supabase-js';

export type ProfileDraft = { username: string; displayName: string; bio: string };
export type Profile = { id: string; username: string | null; displayName: string; bio: string | null };
export type RequestSnapshot = Readonly<{ userId: string; generation: number }>;

export function profilePayload(draft: ProfileDraft): {
  username: string | null;
  display_name: string;
  bio: string | null;
};
export function validateProfileDraft(draft: ProfileDraft): string | null;
export function createLatestRequestGuard(initialUserId: string): {
  begin(): RequestSnapshot;
  accepts(snapshot: RequestSnapshot): boolean;
  switchUser(nextUserId: string): void;
  dispose(): void;
};
export function createExclusiveOperation(): { begin(): boolean; finish(): void };
export function createProfileRepository(client: SupabaseClient, options?: { timeoutMs?: number }): {
  read(userId: string): Promise<
    | { status: 'loaded'; profile: Profile }
    | { status: 'empty' }
    | { status: 'error'; error: unknown }
  >;
  save(userId: string, draft: ProfileDraft): Promise<
    | { status: 'saved'; profile: Profile }
    | { status: 'invalid'; message: string }
    | { status: 'conflict' | 'zero_rows' }
    | { status: 'error'; error: unknown }
    | { status: 'unconfirmed'; reread?: unknown; error?: unknown }
  >;
};
