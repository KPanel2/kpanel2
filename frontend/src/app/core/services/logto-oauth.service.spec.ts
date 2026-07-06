import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import {
  KPANEL_SIGNIN_RESOURCES_KEY,
  LogtoOAuthService,
} from './logto-oauth.service';
import { OidcRuntimeService } from './oidc-runtime.service';
import { environment } from '../../../environments/environment';

function encodePayload(payload: Record<string, unknown>): string {
  const json = JSON.stringify(payload);
  const b64 = btoa(json).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `header.${b64}.signature`;
}

function jsonResponse(body: unknown, ok = true): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status: ok ? 200 : 400 }));
}

describe('LogtoOAuthService', () => {
  let service: LogtoOAuthService;
  let oidcRuntime: { getService: jasmine.Spy };
  let originalAppId: string;
  let originalApiResource: string;
  let originalSecondaryApiResource: string;

  beforeEach(() => {
    originalAppId = environment.logto.appId;
    originalApiResource = environment.logto.apiResource;
    originalSecondaryApiResource = environment.logto.secondaryApiResource;

    environment.logto.appId = 'app-id';
    environment.logto.apiResource = 'https://api.example.com';
    environment.logto.secondaryApiResource = 'https://security.example.com';
    environment.logto.redirectUri = 'http://localhost:8080/callback';
    environment.logto.apiPermissions = ['kpanel:admin'];
    environment.logto.secondaryPermissions = ['securityflags:read'];
    environment.logto.elevatedPermissions = [];

    oidcRuntime = { getService: jasmine.createSpy('getService') };

    TestBed.configureTestingModule({
      providers: [
        LogtoOAuthService,
        { provide: OidcRuntimeService, useValue: oidcRuntime },
      ],
    });

    service = TestBed.inject(LogtoOAuthService);
    sessionStorage.clear();
  });

  afterEach(() => {
    environment.logto.appId = originalAppId;
    environment.logto.apiResource = originalApiResource;
    environment.logto.secondaryApiResource = originalSecondaryApiResource;
    sessionStorage.clear();
  });

  function mockOidc(configId = 'cfg-1') {
    return {
      getConfiguration: () => of({ configId }),
      preloadAuthWellKnownDocument: () => of(true),
      checkAuthMultiple: () => of(true),
      getRefreshToken: () => of('refresh-token'),
    };
  }

  function seedOidcState(configId: string, state: Record<string, unknown>) {
    sessionStorage.setItem(configId, JSON.stringify(state));
  }

  it('no-ops initializeAuth when OIDC is not configured', async () => {
    environment.logto.appId = '';
    await service.initializeAuth();
    expect(oidcRuntime.getService).not.toHaveBeenCalled();
  });

  it('checks stored auth when not on callback', async () => {
    const checkAuthMultiple = jasmine.createSpy('checkAuthMultiple').and.returnValue(of(true));
    oidcRuntime.getService.and.returnValue({ checkAuthMultiple });
    history.replaceState({}, '', '/login');

    await service.initializeAuth();
    expect(checkAuthMultiple).toHaveBeenCalled();
  });

  it('ignores checkAuthMultiple failures on startup', async () => {
    oidcRuntime.getService.and.returnValue({
      checkAuthMultiple: () => throwError(() => new Error('no session')),
    });
    history.replaceState({}, '', '/login');

    await expectAsync(service.initializeAuth()).toBeResolved();
  });

  it('completes callback authorization and cleans URL', async () => {
    const configId = 'cfg-1';
    const state = 'state-123';
    const nonce = 'nonce-123';
    seedOidcState(configId, {
      codeVerifier: 'verifier',
      authStateControl: state,
      authNonce: nonce,
    });
    sessionStorage.setItem(
      KPANEL_SIGNIN_RESOURCES_KEY,
      JSON.stringify(['https://api.example.com', 'https://security.example.com']),
    );
    history.replaceState({}, '', `/callback?code=auth-code&state=${state}`);

    const idToken = encodePayload({ nonce });
    spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({
        access_token: 'access',
        refresh_token: 'refresh',
        id_token: idToken,
        expires_in: 3600,
      }),
    );

    oidcRuntime.getService.and.returnValue(mockOidc(configId));
    await service.initializeAuth();

    const stored = JSON.parse(sessionStorage.getItem(configId) ?? '{}') as {
      authnResult?: { access_token?: string };
    };
    expect(stored.authnResult?.access_token).toBe('access');
    expect(sessionStorage.getItem(KPANEL_SIGNIN_RESOURCES_KEY)).toBeNull();
    expect(window.location.search).toBe('');
  });

  it('rejects callback when sign-in state does not match', async () => {
    seedOidcState('cfg-1', {
      codeVerifier: 'verifier',
      authStateControl: 'expected-state',
      authNonce: 'nonce',
    });
    history.replaceState({}, '', '/callback?code=auth-code&state=wrong-state');
    oidcRuntime.getService.and.returnValue(mockOidc('cfg-1'));

    await expectAsync(service.initializeAuth()).toBeRejectedWithError(/state expired/);
  });

  it('rejects callback token exchange failures', async () => {
    const configId = 'cfg-1';
    seedOidcState(configId, {
      codeVerifier: 'verifier',
      authStateControl: 'state-123',
      authNonce: 'nonce-123',
    });
    history.replaceState({}, '', '/callback?code=auth-code&state=state-123');
    oidcRuntime.getService.and.returnValue(mockOidc(configId));
    spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({ error: 'invalid_grant' }, false),
    );

    await expectAsync(service.initializeAuth()).toBeRejectedWithError(/token exchange/);
  });

  it('rejects incomplete callback token responses', async () => {
    const configId = 'cfg-1';
    seedOidcState(configId, {
      codeVerifier: 'verifier',
      authStateControl: 'state-123',
      authNonce: 'nonce-123',
    });
    history.replaceState({}, '', '/callback?code=auth-code&state=state-123');
    oidcRuntime.getService.and.returnValue(mockOidc(configId));
    spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({ access_token: 'only-access' }),
    );

    await expectAsync(service.initializeAuth()).toBeRejectedWithError(/incomplete token response/);
  });

  it('rejects callback nonce validation failures', async () => {
    const configId = 'cfg-1';
    seedOidcState(configId, {
      codeVerifier: 'verifier',
      authStateControl: 'state-123',
      authNonce: 'expected-nonce',
    });
    history.replaceState({}, '', '/callback?code=auth-code&state=state-123');
    oidcRuntime.getService.and.returnValue(mockOidc(configId));
    spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({
        access_token: 'access',
        refresh_token: 'refresh',
        id_token: encodePayload({ nonce: 'wrong-nonce' }),
      }),
    );

    await expectAsync(service.initializeAuth()).toBeRejectedWithError(/nonce validation/);
  });

  it('throws when callback arrives without OIDC service', async () => {
    history.replaceState({}, '', '/callback?code=auth-code&state=state-123');
    oidcRuntime.getService.and.returnValue(null);

    await expectAsync(service.initializeAuth()).toBeRejectedWithError(/not configured/);
  });

  it('returns early from refresh when configuration is missing', async () => {
    oidcRuntime.getService.and.returnValue({
      getRefreshToken: () => of('refresh-token'),
      getConfiguration: () => of(null),
    });

    await expectAsync(service.refreshOidcSession()).toBeResolved();
  });

  it('ignores refresh responses without an id token', async () => {
    oidcRuntime.getService.and.returnValue(mockOidc('cfg-1'));
    spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({ access_token: 'access-only' }),
    );

    await expectAsync(service.refreshOidcSession()).toBeResolved();
  });

  it('tolerates corrupt stored OIDC state JSON', async () => {
    sessionStorage.setItem('cfg-1', '{not-json');
    oidcRuntime.getService.and.returnValue({
      getConfiguration: () => of({ configId: 'cfg-1' }),
    });

    await service.updateStoredRefreshToken('ignored');
    expect(sessionStorage.getItem('cfg-1')).toBe('{not-json');
  });

  it('rejects sign-in when OIDC runtime is missing', async () => {
    oidcRuntime.getService.and.returnValue(null);
    await expectAsync(service.startSignIn()).toBeRejectedWithError(/not configured/);
  });

  it('rejects sign-in when configuration is missing', async () => {
    oidcRuntime.getService.and.returnValue({
      getConfiguration: () => of(null),
    });
    await expectAsync(service.startSignIn()).toBeRejectedWithError(/not configured/);
  });

  it('returns null refresh token when OIDC is unavailable', async () => {
    oidcRuntime.getService.and.returnValue(null);
    await expectAsync(service.getStoredRefreshToken()).toBeResolvedTo(null);
  });

  it('reads refresh token from OIDC service', async () => {
    oidcRuntime.getService.and.returnValue({
      getRefreshToken: () => of('stored-refresh'),
    });

    await expectAsync(service.getStoredRefreshToken()).toBeResolvedTo('stored-refresh');
  });

  it('refreshes OIDC session with new tokens', async () => {
    const configId = 'cfg-1';
    seedOidcState(configId, { authnResult: { refresh_token: 'old' }, authzData: 'old-access' });
    oidcRuntime.getService.and.returnValue(mockOidc(configId));

    const idToken = encodePayload({ sub: 'user' });
    spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({
        id_token: idToken,
        access_token: 'new-access',
        refresh_token: 'new-refresh',
        expires_in: 3600,
      }),
    );

    await service.refreshOidcSession();

    const stored = JSON.parse(sessionStorage.getItem(configId) ?? '{}') as {
      authnResult?: { id_token?: string; access_token?: string };
      authzData?: string;
    };
    expect(stored.authnResult?.id_token).toBe(idToken);
    expect(stored.authnResult?.access_token).toBe('new-access');
    expect(stored.authzData).toBe('new-access');
  });

  it('returns early from refreshOidcSession without refresh token', async () => {
    oidcRuntime.getService.and.returnValue({
      getRefreshToken: () => of(null),
    });

    await service.refreshOidcSession();
    expect(oidcRuntime.getService).toHaveBeenCalled();
  });

  it('ignores failed refresh responses', async () => {
    oidcRuntime.getService.and.returnValue(mockOidc('cfg-1'));
    spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({ error: 'invalid_grant' }, false),
    );

    await expectAsync(service.refreshOidcSession()).toBeResolved();
  });

  it('updates stored refresh token in OIDC session state', async () => {
    sessionStorage.setItem('cfg-1', JSON.stringify({
      authnResult: { refresh_token: 'old-refresh' },
    }));

    oidcRuntime.getService.and.returnValue({
      getConfiguration: () => of({ configId: 'cfg-1' }),
    });

    await service.updateStoredRefreshToken('new-refresh');
    const stored = JSON.parse(sessionStorage.getItem('cfg-1') ?? '{}') as {
      authnResult?: { refresh_token?: string };
    };
    expect(stored.authnResult?.refresh_token).toBe('new-refresh');
  });

  it('no-ops updateStoredRefreshToken when authn result is missing', async () => {
    oidcRuntime.getService.and.returnValue({
      getConfiguration: () => of({ configId: 'cfg-empty' }),
    });

    await service.updateStoredRefreshToken('ignored');
    expect(sessionStorage.getItem('cfg-empty')).toBeNull();
  });

  it('requests only the primary resource when secondary is unset', async () => {
    environment.logto.secondaryApiResource = '';
    const configId = 'cfg-1';
    seedOidcState(configId, {
      codeVerifier: 'verifier',
      authStateControl: 'state-123',
      authNonce: 'nonce-123',
    });
    history.replaceState({}, '', '/callback?code=auth-code&state=state-123');

    const idToken = encodePayload({ nonce: 'nonce-123' });
    const fetchSpy = spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({
        access_token: 'access',
        refresh_token: 'refresh',
        id_token: idToken,
      }),
    );

    oidcRuntime.getService.and.returnValue(mockOidc(configId));
    await service.initializeAuth();

    const tokenCall = fetchSpy.calls.all().find(call => call.args[0] === 'https://auth.example.com/oidc/token');
    const body = (tokenCall?.args[1] as RequestInit).body as string;
    expect(body).toContain(encodeURIComponent('https://api.example.com'));
    expect(body).not.toContain('security.example.com');
  });

  it('no-ops refreshOidcSession when OIDC is not configured', async () => {
    environment.logto.appId = '';
    await expectAsync(service.refreshOidcSession()).toBeResolved();
  });

  it('falls back to configured resources when sign-in resources are invalid', async () => {
    sessionStorage.setItem(KPANEL_SIGNIN_RESOURCES_KEY, 'not-json');
    const configId = 'cfg-1';
    seedOidcState(configId, {
      codeVerifier: 'verifier',
      authStateControl: 'state-123',
      authNonce: 'nonce-123',
    });
    history.replaceState({}, '', '/callback?code=auth-code&state=state-123');

    const idToken = encodePayload({ nonce: 'nonce-123' });
    const fetchSpy = spyOn(window, 'fetch').and.returnValues(
      jsonResponse({ token_endpoint: 'https://auth.example.com/oidc/token' }),
      jsonResponse({
        access_token: 'access',
        refresh_token: 'refresh',
        id_token: idToken,
      }),
    );

    oidcRuntime.getService.and.returnValue(mockOidc(configId));
    await service.initializeAuth();

    const tokenCall = fetchSpy.calls.all().find(call => call.args[0] === 'https://auth.example.com/oidc/token');
    expect(tokenCall).toBeTruthy();
    const body = (tokenCall?.args[1] as RequestInit).body as string;
    expect(body).toContain(encodeURIComponent('https://api.example.com'));
  });
});
