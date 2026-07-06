import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { authInterceptor } from './auth.interceptor';
import { AuthRequestTraceService } from '../services/auth-request-trace.service';
import { LogtoApiTokenService } from '../services/logto-api-token.service';
import { OidcRuntimeService } from '../services/oidc-runtime.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let tokenService: { token: string | null; secondaryToken: string | null };
  let getIdTokenSpy: jasmine.Spy;

  beforeEach(() => {
    tokenService = { token: 'api-token', secondaryToken: 'sec-token' };
    getIdTokenSpy = jasmine.createSpy('getIdToken').and.returnValue(of('id-token'));

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: LogtoApiTokenService, useValue: tokenService },
        AuthRequestTraceService,
        {
          provide: OidcRuntimeService,
          useValue: {
            getService: () => ({ getIdToken: getIdTokenSpy }),
          },
        },
      ],
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('passes through non-API requests unchanged', () => {
    http.get('/assets/config.json').subscribe();
    const req = httpMock.expectOne('/assets/config.json');
    expect(req.request.headers.has('Authorization')).toBeFalse();
    req.flush({});
  });

  it('attaches auth headers for /api/ requests', () => {
    const trace = TestBed.inject(AuthRequestTraceService);

    http.get('/api/v1/auth/session').subscribe();
    const req = httpMock.expectOne('/api/v1/auth/session');

    expect(req.request.headers.get('Authorization')).toBe('Bearer api-token');
    expect(req.request.headers.get('X-Id-Token')).toBe('id-token');
    expect(req.request.headers.get('X-SecurityFlags-Token')).toBe('sec-token');
    expect(trace.snapshot()).toEqual({
      authorization: true,
      idToken: true,
      securityFlags: true,
    });
    req.flush({});
  });

  it('passes through malformed absolute URLs', () => {
    http.get('http://%').subscribe();
    const req = httpMock.expectOne('http://%');
    expect(req.request.headers.has('Authorization')).toBeFalse();
    req.flush({});
  });

  it('attaches auth headers for absolute same-origin API URLs', () => {
    const url = `${window.location.origin}/api/v1/auth/session`;

    http.get(url).subscribe();
    const req = httpMock.expectOne(url);
    expect(req.request.headers.get('Authorization')).toBe('Bearer api-token');
    req.flush({});
  });

  it('sends without OIDC when runtime service is unavailable', () => {
    TestBed.resetTestingModule();
    tokenService = { token: null, secondaryToken: null };

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: LogtoApiTokenService, useValue: tokenService },
        AuthRequestTraceService,
        {
          provide: OidcRuntimeService,
          useValue: { getService: () => null },
        },
      ],
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    const trace = TestBed.inject(AuthRequestTraceService);

    http.get('/api/v1/foo').subscribe();
    const req = httpMock.expectOne('/api/v1/foo');
    expect(req.request.headers.has('Authorization')).toBeFalse();
    expect(trace.snapshot().authorization).toBeFalse();
    req.flush({});
  });
});
