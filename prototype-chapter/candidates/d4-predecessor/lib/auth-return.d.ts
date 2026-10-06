export type AuthReturnPurpose = 'signup' | 'recovery';

export type ParsedAuthReturn = Readonly<{
  tokenHash: string;
  type: AuthReturnPurpose;
}>;

export type AuthReturnResult =
  | Readonly<{
      status: 'approved';
      purpose: AuthReturnPurpose;
      userId: string;
      sessionMutated: boolean;
      reconciliationNeeded: false;
    }>
  | Readonly<{
      status: 'already_processed';
      code: 'already_processed';
      sessionMutated: false;
      reconciliationNeeded: false;
    }>
  | Readonly<{
      status: 'rejected' | 'reconciliation_needed';
      code: string;
      sessionMutated: boolean;
      reconciliationNeeded: boolean;
    }>;

export class AuthReturnError extends Error {
  readonly code: string;
}

export function parseAuthReturnUrl(rawUrl: string, returnBase: string): ParsedAuthReturn;

export interface AuthReturnAuthClient {
  verifyOtp(params: {
    token_hash: string;
    type: AuthReturnPurpose;
  }): Promise<{
    data: {
      user: { id: string } | null;
      session: unknown | null;
    };
    error: unknown | null;
  }>;
  getUser(): Promise<{
    data: {
      user: {
        id: string;
        email_confirmed_at?: string | null;
      } | null;
    };
    error: unknown | null;
  }>;
}

export function createAuthReturnProcessor(options: {
  auth: AuthReturnAuthClient;
  returnBase: string;
  maxCompleted?: number;
}): Readonly<{
  process(rawUrl: string): Promise<AuthReturnResult>;
}>;
