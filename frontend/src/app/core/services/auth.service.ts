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
import { AuthRequestTraceService } from './auth-request-trace.service';
import { KumpeAccountCenterService } from './kumpe-account-center.service';
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
  private readonly accountCenter = inject(KumpeAccountCenterService);
  private readonly apiTokenService = inject(LogtoApiTokenService);
  private readonly requestTrace = inject(AuthRequestTraceService);
  private readonly _session = new BehaviorSubject<SessionState>(UNAUTHENTICATED_SESSION);
  private securityWatchSub?: Subscription;
  private securityWatchActive = false;
  private accountCenterSuccessKey: string | null = null;

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

  loadSession(options: { refreshClaims?: boolean } = {}): Observable<SessionState> {
    const refreshClaims$ = options.refreshClaims
      ? from(this.logtoOAuth.refreshOidcSession())
      : of(undefined);

    return refreshClaims$.pipe(
      switchMap(() => from(this.prepareAuthHeaders({ includeSecurityFlags: true }))),
      switchMap(({ headers }) => this.api.get<SessionState>('/api/v1/auth/session', headers).pipe(
        map(session => this.applyLocalSecurityPolicy(session)),
        tap(session => this.applySessionState(session)),
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

  /** Refresh KumpeCloud Auth claims and reload the local session (e.g. after Account Center). */
  refreshProfileFromAuth(): Observable<SessionState> {
    return this.loadSession({ refreshClaims: true });
  }

  consumeAccountCenterSuccess(): boolean {
    const params = new URLSearchParams(window.location.search);
    const success = params.get('show_success');
    if (!success) {
      return false;
    }
    this.accountCenterSuccessKey = success;
    params.delete('show_success');
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`;
    window.history.replaceState({}, document.title, nextUrl);
    return true;
  }

  takeAccountCenterSuccessKey(): string | null {
    const key = this.accountCenterSuccessKey;
    this.accountCenterSuccessKey = null;
    return key;
  }

  accountCenterProfileUrl(): string {
    return this.accountCenter.profileUrl({ showSuccess: true });
  }

  accountCenterSecurityUrl(): string {
    return this.accountCenter.securityUrl({ showSuccess: true });
  }

  accountCenterEmailUrl(): string {
    return this.accountCenter.emailUrl({ showSuccess: true });
  }

  bootstrapAfterLogin(options: { refreshClaims?: boolean } = {}): Observable<SessionState> {
    return this.loadSession(options);
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

  private applySessionState(session: SessionState): void {
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
      switchMap(() => (this.isAuthenticated ? this.loadSession({ refreshClaims: true }) : EMPTY)),
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
    this.requestTrace.clear();
    localStorage.removeItem('kpanel_dev_email');
    return this.api.post('/api/v1/auth/logout').pipe(
      tap(() => {
        this._session.next(UNAUTHENTICATED_SESSION);
        this.oidcRuntime.getService()?.logoff().subscribe();
      }),
    );
  }

  createAccount(): Observable<SessionState> {
    return from(this.prepareAuthHeaders({ includeSecurityFlags: true })).pipe(
      switchMap(({ headers }) => this.api.post<SessionState>(
        '/api/v1/account/create',
        {},
        headers,
      ).pipe(
        map(session => this.applyLocalSecurityPolicy(session)),
        tap(session => this.applySessionState(session)),
      )),
    );
  }
}
