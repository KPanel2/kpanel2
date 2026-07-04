import { Injectable, inject } from '@angular/core';
import { HttpHeaders } from '@angular/common/http';
import {
  BehaviorSubject,
  EMPTY,
  Observable,
  Subscription,
  from,
  fromEvent,
  interval,
  merge,
  of,
  switchMap,
} from 'rxjs';
import { catchError, filter, map, tap } from 'rxjs/operators';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
import { AuthDebugService } from './auth-debug.service';
import { AuthRequestTraceService } from './auth-request-trace.service';
import { LogtoApiTokenService } from './logto-api-token.service';
import { LogtoOAuthService } from './logto-oauth.service';
import { OidcRuntimeService } from './oidc-runtime.service';
import { SessionState } from '../models/session.model';
import { isOidcConfigured } from '../../../environments/environment';

const UNAUTHENTICATED_SESSION: SessionState = {
  status: 'unauthenticated',
  permissions: [],
};

const SECURITY_RECHECK_MS = 60_000;

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly oidcRuntime = inject(OidcRuntimeService);
  private readonly logtoOAuth = inject(LogtoOAuthService);
  private readonly apiTokenService = inject(LogtoApiTokenService);
  private readonly authDebug = inject(AuthDebugService);
  private readonly requestTrace = inject(AuthRequestTraceService);
  private readonly _session = new BehaviorSubject<SessionState>(UNAUTHENTICATED_SESSION);
  private securityWatchSub?: Subscription;
  private securityWatchActive = false;

  session$: Observable<SessionState> = this._session.asObservable();

  constructor(private api: ApiService) {}

  get snapshot(): SessionState {
    return this._session.value;
  }

  get isAuthenticated(): boolean {
    return this._session.value?.status === 'authenticated';
  }

  get currentUser() {
    return this._session.value?.user;
  }

  loadSession(): Observable<SessionState> {
    return from(this.prepareAuthHeaders({ includeSecurityFlags: true })).pipe(
      switchMap(({ headers, delivery }) => this.api.get<SessionState>('/api/v1/auth/session', headers).pipe(
        map(session => this.applyLocalSecurityPolicy(session)),
        tap(session => this.applySessionState(session, delivery)),
      )),
      catchError((err: unknown) => {
        const message = err instanceof Error ? err.message : 'Failed to load session.';
        const session: SessionState = {
          status: 'unauthenticated',
          permissions: [],
          message,
        };
        this._session.next(session);
        return of(session);
      }),
    );
  }

  bootstrapAfterLogin(): Observable<SessionState> {
    return this.loadSession();
  }

  private async prepareAuthHeaders(options: { includeSecurityFlags?: boolean } = {}): Promise<{
    headers?: HttpHeaders;
    delivery: { authorization: boolean; idToken: boolean; securityFlags: boolean };
  }> {
    const includeSecurityFlags = options.includeSecurityFlags ?? false;
    const oidc = this.oidcRuntime.getService();
    if (!oidc) {
      return { delivery: { authorization: false, idToken: false, securityFlags: false } };
    }

    await this.apiTokenService.ensureApiResourceTokens({ includeSecondary: includeSecurityFlags });

    const idToken = await firstValueFrom(oidc.getIdToken());
    const headers = this.apiTokenService.buildAuthHeaders(idToken, { includeSecurityFlags });
    const delivery = this.apiTokenService.describeAuthHeaders(idToken, { includeSecurityFlags });
    this.requestTrace.record(delivery);
    return { headers, delivery };
  }

  private applyLocalSecurityPolicy(session: SessionState): SessionState {
    const localDenial = this.apiTokenService.evaluateLocalSecurityDenial();
    if (localDenial) {
      return localDenial;
    }
    return session;
  }

  private applySessionState(
    session: SessionState,
    delivery?: { authorization: boolean; idToken: boolean; securityFlags: boolean },
  ): void {
    void this.authDebug.capture(session, delivery);
    if (session.status === 'access_denied') {
      this.stopSecurityWatch();
      this._session.next(session);
      return;
    }
    this._session.next(session);
    if (session.status === 'authenticated' && isOidcConfigured()) {
      this.startSecurityWatch();
    }
  }

  private startSecurityWatch(): void {
    if (this.securityWatchActive) {
      return;
    }
    this.securityWatchActive = true;
    this.securityWatchSub?.unsubscribe();
    this.securityWatchSub = merge(
      interval(SECURITY_RECHECK_MS),
      fromEvent(window, 'focus'),
      fromEvent(document, 'visibilitychange').pipe(
        filter(() => document.visibilityState === 'visible'),
      ),
    ).pipe(
      switchMap(() => (this.isAuthenticated ? this.loadSession() : EMPTY)),
    ).subscribe();
  }

  private stopSecurityWatch(): void {
    this.securityWatchActive = false;
    this.securityWatchSub?.unsubscribe();
    this.securityWatchSub = undefined;
  }

  signIn(): Promise<void> {
    if (!isOidcConfigured()) {
      return Promise.reject(
        new Error('KumpeCloud sign-in is not configured. Set KPANEL_LOGTO_APP_ID on the backend.'),
      );
    }
    return this.logtoOAuth.startSignIn();
  }

  logout(): Observable<unknown> {
    this.stopSecurityWatch();
    this.apiTokenService.clear();
    this.authDebug.clear();
    this.requestTrace.clear();
    localStorage.removeItem('kpanel_dev_email');
    return this.api.post('/api/v1/auth/logout').pipe(
      tap(() => {
        this._session.next(UNAUTHENTICATED_SESSION);
        this.oidcRuntime.getService()?.logoff().subscribe();
      }),
    );
  }

  createAccount(displayName: string, timezone: string): Observable<SessionState> {
    return from(this.prepareAuthHeaders({ includeSecurityFlags: true })).pipe(
      switchMap(({ headers, delivery }) => this.api.post<SessionState>(
        '/api/v1/account/create',
        { display_name: displayName, timezone },
        headers,
      ).pipe(
        map(session => this.applyLocalSecurityPolicy(session)),
        tap(session => this.applySessionState(session, delivery)),
      )),
    );
  }

  updateProfile(displayName: string, timezone: string): Observable<SessionState> {
    return from(this.prepareAuthHeaders({ includeSecurityFlags: false })).pipe(
      switchMap(({ headers }) => this.api.patch<SessionState>(
        '/api/v1/account/profile',
        { timezone },
        headers,
      ).pipe(tap(session => this._session.next(session)))),
    );
  }
}
