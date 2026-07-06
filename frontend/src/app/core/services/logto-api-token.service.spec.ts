import { TestBed } from '@angular/core/testing';

import { LogtoApiTokenService } from './logto-api-token.service';
import { LogtoOAuthService } from './logto-oauth.service';
import { environment } from '../../../environments/environment';

function encodePayload(payload: Record<string, unknown>): string {
  const json = JSON.stringify(payload);
  const b64 = btoa(json).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `header.${b64}.signature`;
}

function tokenResponse(accessToken: string, refreshToken = 'rotated-refresh') {
  return { accessToken, refreshToken };
}

describe('LogtoApiTokenService', () => {
  let service: LogtoApiTokenService;
  let logtoOAuth: jasmine.SpyObj<LogtoOAuthService>;
  let requestResourceTokenSpy: jasmine.Spy;
  let originalApiResource: string;
  let originalSecondaryResource: string;

  beforeEach(() => {
    originalApiResource = environment.logto.apiResource;
    originalSecondaryResource = environment.logto.secondaryApiResource;
    environment.logto.apiResource = 'https://api.example.com';
    environment.logto.secondaryApiResource = 'https://security.example.com';
    environment.logto.appId = 'app-id';

    logtoOAuth = jasmine.createSpyObj<LogtoOAuthService>('LogtoOAuthService', [
      'getStoredRefreshToken',
      'updateStoredRefreshToken',
    ]);
    logtoOAuth.getStoredRefreshToken.and.returnValue(Promise.resolve('refresh-token'));
    logtoOAuth.updateStoredRefreshToken.and.returnValue(Promise.resolve());

    TestBed.configureTestingModule({
      providers: [
        LogtoApiTokenService,
        { provide: LogtoOAuthService, useValue: logtoOAuth },
      ],
    });

    service = TestBed.inject(LogtoApiTokenService);
    requestResourceTokenSpy = spyOn(
      service as unknown as { requestResourceToken: (resource: string) => Promise<unknown> },
      'requestResourceToken',
    ).and.returnValue(
      Promise.resolve(tokenResponse(encodePayload({ exp: Math.floor(Date.now() / 1000) + 3600 }))),
    );
  });

  afterEach(() => {
    environment.logto.apiResource = originalApiResource;
    environment.logto.secondaryApiResource = originalSecondaryResource;
  });

  it('clears cached tokens', () => {
    service.clear();
    expect(service.token).toBeNull();
    expect(service.secondaryToken).toBeNull();
  });

  it('fetches primary and secondary resource tokens', async () => {
    await service.ensureApiResourceTokens({ includeSecondary: true });

    expect(requestResourceTokenSpy).toHaveBeenCalledTimes(2);
    expect(service.token).toBeTruthy();
    expect(service.secondaryToken).toBeTruthy();
    expect(logtoOAuth.updateStoredRefreshToken).toHaveBeenCalledWith('rotated-refresh');
  });

  it('skips refresh when tokens are still valid', async () => {
    const validToken = encodePayload({ exp: Math.floor(Date.now() / 1000) + 3600 });
    requestResourceTokenSpy.and.returnValue(Promise.resolve(tokenResponse(validToken)));

    await service.ensureApiResourceTokens({ includeSecondary: true });
    requestResourceTokenSpy.calls.reset();

    await service.ensureApiResourceTokens({ includeSecondary: true });
    expect(requestResourceTokenSpy).not.toHaveBeenCalled();
  });

  it('builds and describes auth headers', async () => {
    const validToken = encodePayload({ exp: Math.floor(Date.now() / 1000) + 3600 });
    requestResourceTokenSpy.and.returnValue(Promise.resolve(tokenResponse(validToken)));

    await service.ensureApiResourceTokens({ includeSecondary: true });

    const headers = service.buildAuthHeaders('id-token', { includeSecurityFlags: true });
    expect(headers.get('Authorization')).toContain('Bearer');
    expect(headers.get('X-Id-Token')).toBe('id-token');
    expect(headers.get('X-SecurityFlags-Token')).toBeTruthy();

    expect(service.describeAuthHeaders('id-token')).toEqual({
      authorization: true,
      idToken: true,
      securityFlags: true,
    });
  });

  it('denies access for blocking security flags in secondary token', async () => {
    const blockedToken = encodePayload({
      exp: Math.floor(Date.now() / 1000) + 3600,
      scope: 'securityflags:fraud',
    });
    let callCount = 0;
    requestResourceTokenSpy.and.callFake(() => {
      callCount += 1;
      return Promise.resolve(tokenResponse(
        callCount === 1
          ? encodePayload({ exp: Math.floor(Date.now() / 1000) + 3600 })
          : blockedToken,
      ));
    });

    await service.ensureApiResourceTokens({ includeSecondary: true });
    const denial = service.evaluateLocalSecurityDenial();

    expect(denial?.status).toBe('access_denied');
    expect(denial?.message).toContain('fraud');
  });

  it('throws when refresh token is missing', async () => {
    logtoOAuth.getStoredRefreshToken.and.returnValue(Promise.resolve(null));
    requestResourceTokenSpy.and.callThrough();

    await expectAsync(service.ensureApiResourceTokens()).toBeRejectedWithError(/session expired/);
  });

  it('continues when secondary token fetch fails', async () => {
    let callCount = 0;
    requestResourceTokenSpy.and.callFake(() => {
      callCount += 1;
      if (callCount === 2) {
        return Promise.reject(new Error('secondary unavailable'));
      }
      return Promise.resolve(tokenResponse(
        encodePayload({ exp: Math.floor(Date.now() / 1000) + 3600 }),
      ));
    });

    await service.ensureApiResourceTokens({ includeSecondary: true });
    expect(service.token).toBeTruthy();
    expect(service.secondaryToken).toBeNull();
  });

  it('maps token endpoint failures to friendly errors', async () => {
    requestResourceTokenSpy.and.callThrough();
    spyOn(window, 'fetch').and.resolveTo(new Response('{"error":"invalid_target"}', { status: 400 }));

    await expectAsync(service.ensureApiResourceTokens()).toBeRejectedWithError(/API resource indicator/);
  });

  it('treats tokens without exp as valid', async () => {
    requestResourceTokenSpy.and.returnValue(Promise.resolve(tokenResponse(encodePayload({ sub: 'user' }))));

    await service.ensureApiResourceTokens();
    expect(service.token).toBeTruthy();
  });

  it('can omit security flag headers when disabled', async () => {
    const validToken = encodePayload({ exp: Math.floor(Date.now() / 1000) + 3600 });
    requestResourceTokenSpy.and.returnValue(Promise.resolve(tokenResponse(validToken)));

    await service.ensureApiResourceTokens({ includeSecondary: true });
    expect(service.describeAuthHeaders('id-token', { includeSecurityFlags: false })).toEqual({
      authorization: true,
      idToken: true,
      securityFlags: false,
    });
    const headers = service.buildAuthHeaders('id-token', { includeSecurityFlags: false });
    expect(headers.has('X-SecurityFlags-Token')).toBeFalse();
  });
});
