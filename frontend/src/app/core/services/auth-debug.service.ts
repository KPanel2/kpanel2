import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';
import { decodeJwtPayload, scopeClaimToList } from '../../utils/jwt-decode';
import { SessionState } from '../models/session.model';
import { LogtoApiTokenService } from './logto-api-token.service';
import { OidcRuntimeService } from './oidc-runtime.service';
import { AuthRequestTraceService } from './auth-request-trace.service';

export const KPANEL_AUTH_DEBUG_KEY = 'kpanel_auth_debug';

export type TokenDebugInfo = {
  present: boolean;
  aud: unknown;
  scope: string[];
  roles: unknown;
  sub: string | null;
  payload: Record<string, unknown> | null;
};

export type AuthDebugSnapshot = {
  capturedAt: string;
  sessionStatus: string;
  sessionMessage?: string;
  sessionPermissions: string[];
  serverDebug?: Record<string, unknown>;
  tokens: {
    idToken: TokenDebugInfo;
    apiAccessToken: TokenDebugInfo;
    securityFlagsToken: TokenDebugInfo;
  };
  delivery: {
    apiBearerSent: boolean;
    securityFlagsHeaderSent: boolean;
    /** Headers actually attached to the last /api request (may differ from in-memory tokens). */
    lastRequestHeaders?: {
      authorization: boolean;
      idToken: boolean;
      securityFlags: boolean;
    };
  };
};

@Injectable({ providedIn: 'root' })
export class AuthDebugService {
  private readonly oidcRuntime = inject(OidcRuntimeService);
  private readonly apiTokenService = inject(LogtoApiTokenService);
  private readonly requestTrace = inject(AuthRequestTraceService);

  isEnabled(): boolean {
    return environment.authDebugEnabled || !environment.production;
  }

  readSnapshot(): AuthDebugSnapshot | null {
    if (!this.isEnabled()) {
      return null;
    }

    const raw = sessionStorage.getItem(KPANEL_AUTH_DEBUG_KEY);
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as AuthDebugSnapshot;
    } catch {
      return null;
    }
  }

  clear(): void {
    sessionStorage.removeItem(KPANEL_AUTH_DEBUG_KEY);
  }

  async capture(
    session?: SessionState,
    delivery?: { authorization: boolean; idToken: boolean; securityFlags: boolean },
  ): Promise<void> {
    if (!this.isEnabled()) {
      return;
    }

    const oidc = this.oidcRuntime.getService();
    const idToken = oidc ? await firstValueFrom(oidc.getIdToken()) : null;
    const apiToken = this.apiTokenService.token;
    const securityToken = this.apiTokenService.secondaryToken;

    const snapshot: AuthDebugSnapshot = {
      capturedAt: new Date().toISOString(),
      sessionStatus: session?.status ?? 'unknown',
      sessionMessage: session?.message,
      sessionPermissions: session?.permissions ?? [],
      serverDebug: session?.debug,
      tokens: {
        idToken: this.describeToken(idToken),
        apiAccessToken: this.describeToken(apiToken),
        securityFlagsToken: this.describeToken(securityToken),
      },
      delivery: {
        apiBearerSent: delivery?.authorization ?? Boolean(apiToken),
        securityFlagsHeaderSent: delivery?.securityFlags ?? Boolean(securityToken),
        lastRequestHeaders: delivery ?? this.requestTrace.snapshot(),
      },
    };

    sessionStorage.setItem(KPANEL_AUTH_DEBUG_KEY, JSON.stringify(snapshot, null, 2));
  }

  private describeToken(token: string | null | undefined): TokenDebugInfo {
    const payload = decodeJwtPayload(token);
    return {
      present: Boolean(token?.trim()),
      aud: payload?.['aud'] ?? null,
      scope: scopeClaimToList(payload?.['scope']),
      roles: payload?.['roles'] ?? null,
      sub: typeof payload?.['sub'] === 'string' ? payload['sub'] : null,
      payload,
    };
  }
}
