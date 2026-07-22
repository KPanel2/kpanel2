import { HttpHeaders } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { BehaviorSubject, firstValueFrom, of, throwError } from 'rxjs';

import { AuthService } from './auth.service';
import { ApiService } from './api.service';
import { AuthRequestTraceService } from './auth-request-trace.service';
import { KumpeAccountCenterService } from './kumpe-account-center.service';
import { LogtoApiTokenService } from './logto-api-token.service';
import { LogtoOAuthService } from './logto-oauth.service';
import { OidcRuntimeService } from './oidc-runtime.service';
import { SessionState } from '../models/session.model';
import { environment } from '../../../environments/environment';

describe('AuthService', () => {
  let service: AuthService;
  let api: jasmine.SpyObj<ApiService>;
  let oidcRuntime: { getService: jasmine.Spy };
  let logtoOAuth: jasmine.SpyObj<LogtoOAuthService>;
  let accountCenter: jasmine.SpyObj<KumpeAccountCenterService>;
  let apiTokenService: jasmine.SpyObj<LogtoApiTokenService>;
  let requestTrace: AuthRequestTraceService;
  let originalAppId: string;

  const AUTHENTICATED: SessionState = {
    status: 'authenticated',
    permissions: ['kpanel:admin'],
    user: {
      id: 1,
      email: 'user@example.com',
      display_name: 'User',
      timezone: 'UTC',
      identities: [],
      devices: [],
    },
  };

  beforeEach(() => {
    originalAppId = environment.logto.appId;
    environment.logto.appId = '';

    api = jasmine.createSpyObj<ApiService>('ApiService', ['get', 'post', 'patch']);
    oidcRuntime = { getService: jasmine.createSpy('getService').and.returnValue(null) };
    logtoOAuth = jasmine.createSpyObj<LogtoOAuthService>('LogtoOAuthService', [
      'refreshOidcSession',
      'startSignIn',
    ]);
    logtoOAuth.refreshOidcSession.and.returnValue(Promise.resolve());
    accountCenter = jasmine.createSpyObj<KumpeAccountCenterService>('KumpeAccountCenterService', [
      'profileUrl',
      'securityUrl',
      'emailUrl',
    ]);
    accountCenter.profileUrl.and.returnValue('https://auth.example/account/profile');
    accountCenter.securityUrl.and.returnValue('https://auth.example/account/security');
    accountCenter.emailUrl.and.returnValue('https://auth.example/account/email');

    apiTokenService = jasmine.createSpyObj<LogtoApiTokenService>('LogtoApiTokenService', [
      'ensureApiResourceTokens',
      'buildAuthHeaders',
      'describeAuthHeaders',
      'evaluateLocalSecurityDenial',
      'clear',
    ]);
    apiTokenService.ensureApiResourceTokens.and.returnValue(Promise.resolve());
    apiTokenService.buildAuthHeaders.and.returnValue(new HttpHeaders({ Authorization: 'Bearer token' }));
    apiTokenService.describeAuthHeaders.and.returnValue({
      authorization: true,
      idToken: false,
      securityFlags: false,
    });
    apiTokenService.evaluateLocalSecurityDenial.and.returnValue(null);

    TestBed.configureTestingModule({
      providers: [
        AuthService,
        AuthRequestTraceService,
        { provide: ApiService, useValue: api },
        { provide: OidcRuntimeService, useValue: oidcRuntime },
        { provide: LogtoOAuthService, useValue: logtoOAuth },
        { provide: KumpeAccountCenterService, useValue: accountCenter },
        { provide: LogtoApiTokenService, useValue: apiTokenService },
      ],
    });

    service = TestBed.inject(AuthService);
    requestTrace = TestBed.inject(AuthRequestTraceService);
  });

  afterEach(() => {
    environment.logto.appId = originalAppId;
    localStorage.removeItem('kpanel_dev_email');
  });

  it('exposes session snapshot helpers', () => {
    expect(service.isAuthenticated).toBeFalse();
    expect(service.authReady).toBeFalse();
    expect(service.currentUser).toBeUndefined();
  });

  it('loads session and marks user authenticated', (done) => {
    api.get.and.returnValue(of(AUTHENTICATED));

    service.loadSession().subscribe(session => {
      expect(session.status).toBe('authenticated');
      expect(service.isAuthenticated).toBeTrue();
      expect(service.currentUser?.email).toBe('user@example.com');
      done();
    });
  });

  it('returns unauthenticated session on load failure', (done) => {
    api.get.and.returnValue(throwError(() => new Error('Network down')));

    service.loadSession().subscribe(session => {
      expect(session.status).toBe('unauthenticated');
      expect(session.message).toBe('Network down');
      done();
    });
  });

  it('returns generic message for non-Error load failures', (done) => {
    api.get.and.returnValue(throwError(() => 'boom'));

    service.loadSession().subscribe(session => {
      expect(session.message).toBe('Failed to load session.');
      done();
    });
  });

  it('applies local security denial before session state', (done) => {
    const denied: SessionState = {
      status: 'access_denied',
      permissions: [],
      message: 'Blocked',
    };
    apiTokenService.evaluateLocalSecurityDenial.and.returnValue(denied);
    api.get.and.returnValue(of(AUTHENTICATED));

    service.loadSession().subscribe(session => {
      expect(session).toEqual(denied);
      expect(service.snapshot.status).toBe('access_denied');
      done();
    });
  });

  it('delegates bootstrapAfterLogin to loadSession', (done) => {
    api.get.and.returnValue(of(AUTHENTICATED));

    service.bootstrapAfterLogin().subscribe(session => {
      expect(session.status).toBe('authenticated');
      done();
    });
  });

  it('bootstraps through OIDC when authenticated', async () => {
    const oidc = {
      isAuthenticated: () => of(true),
      getIdToken: () => of('id-token'),
    };
    oidcRuntime.getService.and.returnValue(oidc);
    api.get.and.returnValue(of(AUTHENTICATED));

    await firstValueFrom(service.bootstrapApp());
    expect(service.authReady).toBeTrue();
  });

  it('bootstraps without OIDC and marks auth ready', async () => {
    api.get.and.returnValue(of({ status: 'unauthenticated', permissions: [] }));

    await firstValueFrom(service.bootstrapApp());
    expect(service.authReady).toBeTrue();
  });

  it('rejects sign-in when OIDC is not configured', async () => {
    await expectAsync(service.signIn()).toBeRejectedWithError(/not configured/);
  });

  it('starts OIDC sign-in when configured', async () => {
    environment.logto.appId = 'app-id';
    logtoOAuth.startSignIn.and.returnValue(Promise.resolve());

    await service.signIn();
    expect(logtoOAuth.startSignIn).toHaveBeenCalled();
  });

  it('logs out and clears local auth state', (done) => {
    api.post.and.returnValue(of({}));
    oidcRuntime.getService.and.returnValue({ logoff: () => of(true) });

    service.logout().subscribe(() => {
      expect(apiTokenService.clear).toHaveBeenCalled();
      expect(requestTrace.snapshot().authorization).toBeFalse();
      expect(service.snapshot.status).toBe('unauthenticated');
      done();
    });
  });

  it('creates an account with auth headers', (done) => {
    oidcRuntime.getService.and.returnValue({
      getIdToken: () => of('id-token'),
    });
    api.post.and.returnValue(of(AUTHENTICATED));

    service.createAccount().subscribe(session => {
      expect(apiTokenService.ensureApiResourceTokens).toHaveBeenCalled();
      expect(api.post).toHaveBeenCalledWith('/api/v1/account/create', {}, jasmine.any(HttpHeaders));
      expect(session.status).toBe('authenticated');
      done();
    });
  });

  it('does not consume account center success when absent', () => {
    history.replaceState({}, '', '/dashboard');
    expect(service.consumeAccountCenterSuccess()).toBeFalse();
  });

  it('consumes account center success query param', () => {
    history.replaceState({}, '', '/dashboard?show_success=profile-updated&tab=1');

    expect(service.consumeAccountCenterSuccess()).toBeTrue();
    expect(service.takeAccountCenterSuccessKey()).toBe('profile-updated');
    expect(window.location.search).not.toContain('show_success');
  });

  it('returns null when no account center success was consumed', () => {
    expect(service.takeAccountCenterSuccessKey()).toBeNull();
  });

  it('returns account center URLs with success flag', () => {
    service.accountCenterProfileUrl();
    service.accountCenterSecurityUrl();
    service.accountCenterEmailUrl();

    expect(accountCenter.profileUrl).toHaveBeenCalledWith({ showSuccess: true });
    expect(accountCenter.securityUrl).toHaveBeenCalledWith({ showSuccess: true });
    expect(accountCenter.emailUrl).toHaveBeenCalledWith({ showSuccess: true });
  });

  it('refreshes profile from auth provider', (done) => {
    api.get.and.returnValue(of(AUTHENTICATED));

    service.refreshProfileFromAuth().subscribe(() => {
      expect(logtoOAuth.refreshOidcSession).toHaveBeenCalled();
      done();
    });
  });

  it('loads session with refreshed claims when requested', (done) => {
    api.get.and.returnValue(of(AUTHENTICATED));

    service.loadSession({ refreshClaims: true }).subscribe(() => {
      expect(logtoOAuth.refreshOidcSession).toHaveBeenCalled();
      done();
    });
  });

  it('stops security watch for access_denied sessions', (done) => {
    api.get.and.returnValue(of({
      status: 'access_denied',
      permissions: [],
      message: 'Denied',
    }));

    service.loadSession().subscribe(session => {
      expect(session.status).toBe('access_denied');
      done();
    });
  });

  it('updates account HA binding via profile patch', (done) => {
    const updated = {
      ...AUTHENTICATED,
      user: {
        ...AUTHENTICATED.user!,
        ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
        has_ha_binding: true,
      },
    };
    api.patch.and.returnValue(of(updated));

    service.updateHaBinding({
      ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
      ha_binding_secret: 'secret',
    }).subscribe(session => {
      expect(api.patch).toHaveBeenCalledWith('/api/v1/account/profile', {
        ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
        ha_binding_secret: 'secret',
      });
      expect(session.user?.has_ha_binding).toBeTrue();
      done();
    });
  });
});
