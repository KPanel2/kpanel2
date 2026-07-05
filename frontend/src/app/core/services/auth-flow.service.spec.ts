import {
  AuthFlowService,
  resolveLoginViewPhase,
  resolveSessionNavigation,
  shouldAutoRedirectToOidc,
} from './auth-flow.service';
import { SessionState } from '../models/session.model';

const UNAUTHENTICATED: SessionState = { status: 'unauthenticated', permissions: [] };
const AUTHENTICATED: SessionState = { status: 'authenticated', permissions: [], user: undefined };
const ACCESS_DENIED: SessionState = { status: 'access_denied', permissions: [], message: 'Denied' };
const NEEDS_ACCOUNT: SessionState = {
  status: 'needs_account',
  permissions: [],
  pending: { provider_name: 'logto', email: 'a@b.com' },
};

function loginContext(overrides: Partial<Parameters<typeof resolveLoginViewPhase>[0]> = {}) {
  return {
    authReady: false,
    session: UNAUTHENTICATED,
    oidcConfigured: true,
    devAuthEnabled: false,
    redirecting: false,
    redirectError: '',
    ...overrides,
  };
}

describe('AuthFlowService helpers', () => {
  describe('resolveLoginViewPhase', () => {
    it('shows checking UI during bootstrap', () => {
      expect(resolveLoginViewPhase(loginContext({ authReady: false }))).toBe('checking');
    });

    it('shows checking UI for authenticated users on login until navigation', () => {
      expect(resolveLoginViewPhase(loginContext({
        authReady: true,
        session: AUTHENTICATED,
      }))).toBe('checking');
    });

    it('shows redirecting while OIDC redirect is in progress', () => {
      expect(resolveLoginViewPhase(loginContext({
        authReady: true,
        redirecting: true,
      }))).toBe('redirecting');
    });

    it('prepares redirecting state for unauthenticated OIDC users', () => {
      expect(resolveLoginViewPhase(loginContext({
        authReady: true,
        oidcConfigured: true,
      }))).toBe('redirecting');
    });

    it('shows access_denied UI without redirect', () => {
      expect(resolveLoginViewPhase(loginContext({
        authReady: true,
        session: ACCESS_DENIED,
      }))).toBe('access_denied');
    });

    it('shows needs_account UI without redirect', () => {
      expect(resolveLoginViewPhase(loginContext({
        authReady: true,
        session: NEEDS_ACCOUNT,
      }))).toBe('needs_account');
    });

    it('shows dev sign-in when dev auth is enabled without OIDC', () => {
      expect(resolveLoginViewPhase(loginContext({
        authReady: true,
        oidcConfigured: false,
        devAuthEnabled: true,
      }))).toBe('dev_sign_in');
    });

    it('shows OIDC fallback after redirect error', () => {
      expect(resolveLoginViewPhase(loginContext({
        authReady: true,
        redirectError: 'Sign-in failed',
      }))).toBe('oidc_fallback');
    });

    it('shows unconfigured when neither OIDC nor dev auth is available', () => {
      expect(resolveLoginViewPhase(loginContext({
        authReady: true,
        oidcConfigured: false,
        devAuthEnabled: false,
      }))).toBe('unconfigured');
    });
  });

  describe('shouldAutoRedirectToOidc', () => {
    it('triggers auto-redirect for unauthenticated OIDC users after bootstrap', () => {
      expect(shouldAutoRedirectToOidc(loginContext({
        authReady: true,
        oidcConfigured: true,
      }))).toBeTrue();
    });

    it('does not auto-redirect during bootstrap', () => {
      expect(shouldAutoRedirectToOidc(loginContext({
        authReady: false,
        oidcConfigured: true,
      }))).toBeFalse();
    });

    it('does not auto-redirect for access_denied', () => {
      expect(shouldAutoRedirectToOidc(loginContext({
        authReady: true,
        session: ACCESS_DENIED,
      }))).toBeFalse();
    });

    it('does not auto-redirect for needs_account', () => {
      expect(shouldAutoRedirectToOidc(loginContext({
        authReady: true,
        session: NEEDS_ACCOUNT,
      }))).toBeFalse();
    });

    it('does not auto-redirect in dev-auth-only mode', () => {
      expect(shouldAutoRedirectToOidc(loginContext({
        authReady: true,
        oidcConfigured: false,
        devAuthEnabled: true,
      }))).toBeFalse();
    });

    it('does not auto-redirect while redirect is already in progress', () => {
      expect(shouldAutoRedirectToOidc(loginContext({
        authReady: true,
        redirecting: true,
      }))).toBeFalse();
    });

    it('does not auto-redirect after a redirect error', () => {
      expect(shouldAutoRedirectToOidc(loginContext({
        authReady: true,
        redirectError: 'Failed',
      }))).toBeFalse();
    });
  });

  describe('resolveSessionNavigation', () => {
    it('does not navigate before bootstrap completes', () => {
      expect(resolveSessionNavigation(UNAUTHENTICATED, '/', false)).toBeNull();
    });

    it('routes authenticated users away from login', () => {
      expect(resolveSessionNavigation(AUTHENTICATED, '/login', true)).toBe('/');
    });

    it('routes access_denied users to login', () => {
      expect(resolveSessionNavigation(ACCESS_DENIED, '/', true)).toBe('/login');
    });

    it('routes unauthenticated users to login except on callback', () => {
      expect(resolveSessionNavigation(UNAUTHENTICATED, '/', true)).toBe('/login');
      expect(resolveSessionNavigation(UNAUTHENTICATED, '/callback', true)).toBeNull();
      expect(resolveSessionNavigation(UNAUTHENTICATED, '/login', true)).toBeNull();
    });
  });
});

describe('AuthFlowService', () => {
  it('exposes helper methods', () => {
    const service = new AuthFlowService();
    expect(service.resolveLoginViewPhase(loginContext())).toBe('checking');
  });
});
