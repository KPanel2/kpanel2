import { Injectable, inject } from '@angular/core';
import { HttpHeaders } from '@angular/common/http';
import { fetchTokenByRefreshToken } from '@logto/js';

import { environment } from '../../../environments/environment';
import {
  findBlockingSecurityFlags,
  securityFlagDenialMessage,
} from '../security-flags';
import { SessionState } from '../models/session.model';
import { decodeJwtPayload, scopeClaimToList } from '../../utils/jwt-decode';
import { normalizeLogtoResource, parseLogtoTokenError } from '../../utils/logto-resource';
import { LogtoOAuthService } from './logto-oauth.service';

type ResourceTokenResponse = {
  accessToken: string;
  refreshToken?: string;
};

export type EnsureApiTokensOptions = {
  /** Refresh the securityflags API token (session checks only — avoids extra refresh grants). */
  includeSecondary?: boolean;
};

/**
 * Fetches per-resource API access tokens via refresh token (RFC 8707).
 *
 * Refresh grants are serialized and always read the latest stored refresh token so
 * Logto's rotation does not trigger invalid_grant from concurrent or stale reuse.
 */
@Injectable({ providedIn: 'root' })
export class LogtoApiTokenService {
  private readonly logtoOAuth = inject(LogtoOAuthService);
  private apiAccessToken: string | null = null;
  private secondaryAccessToken: string | null = null;
  private refreshChain: Promise<void> = Promise.resolve();

  get token(): string | null {
    return this.apiAccessToken;
  }

  get secondaryToken(): string | null {
    return this.secondaryAccessToken;
  }

  clear(): void {
    this.apiAccessToken = null;
    this.secondaryAccessToken = null;
    this.refreshChain = Promise.resolve();
  }

  ensureApiResourceTokens(options: EnsureApiTokensOptions = {}): Promise<void> {
    if (this.hasFreshTokens(options)) {
      return Promise.resolve();
    }

    this.refreshChain = this.refreshChain
      .then(() => this.refreshTokens(options))
      .catch(err => {
        this.refreshChain = Promise.resolve();
        throw err;
      });
    return this.refreshChain;
  }

  private hasFreshTokens(options: EnsureApiTokensOptions): boolean {
    if (!this.isTokenValid(this.apiAccessToken)) {
      return false;
    }

    const secondaryResource = environment.logto.secondaryApiResource?.trim();
    if (options.includeSecondary && secondaryResource && !this.isTokenValid(this.secondaryAccessToken)) {
      return false;
    }

    return true;
  }

  private async refreshTokens(options: EnsureApiTokensOptions): Promise<void> {
    const secondaryResource = environment.logto.secondaryApiResource?.trim();
    const includeSecondary = Boolean(options.includeSecondary && secondaryResource);

    if (!this.isTokenValid(this.apiAccessToken)) {
      const primary = await this.requestResourceToken(environment.logto.apiResource);
      this.apiAccessToken = primary.accessToken;
      if (primary.refreshToken) {
        await this.logtoOAuth.updateStoredRefreshToken(primary.refreshToken);
      }
    }

    if (!includeSecondary) {
      return;
    }

    if (this.isTokenValid(this.secondaryAccessToken)) {
      return;
    }

    try {
      const secondary = await this.requestResourceToken(secondaryResource!);
      this.secondaryAccessToken = secondary.accessToken;
      if (secondary.refreshToken) {
        await this.logtoOAuth.updateStoredRefreshToken(secondary.refreshToken);
      }
    } catch (err) {
      console.warn('Securityflags API token unavailable; blocking flags cannot be checked:', err);
      this.secondaryAccessToken = null;
    }
  }

  private isTokenValid(token: string | null, skewSeconds = 60): boolean {
    if (!token) {
      return false;
    }
    const payload = decodeJwtPayload(token);
    const exp = payload?.['exp'];
    if (typeof exp !== 'number') {
      return true;
    }
    return Date.now() / 1000 < exp - skewSeconds;
  }

  buildAuthHeaders(idToken?: string | null, options: { includeSecurityFlags?: boolean } = {}): HttpHeaders {
    const includeSecurityFlags = options.includeSecurityFlags ?? true;
    let headers = new HttpHeaders();
    if (this.apiAccessToken) {
      headers = headers.set('Authorization', `Bearer ${this.apiAccessToken}`);
    }
    if (idToken?.trim()) {
      headers = headers.set('X-Id-Token', idToken.trim());
    }
    if (includeSecurityFlags && this.secondaryAccessToken) {
      headers = headers.set('X-SecurityFlags-Token', this.secondaryAccessToken);
    }
    return headers;
  }

  describeAuthHeaders(
    idToken?: string | null,
    options: { includeSecurityFlags?: boolean } = {},
  ): {
    authorization: boolean;
    idToken: boolean;
    securityFlags: boolean;
  } {
    const includeSecurityFlags = options.includeSecurityFlags ?? true;
    return {
      authorization: Boolean(this.apiAccessToken),
      idToken: Boolean(idToken?.trim()),
      securityFlags: includeSecurityFlags && Boolean(this.secondaryAccessToken),
    };
  }

  evaluateLocalSecurityDenial(): SessionState | null {
    if (!this.secondaryAccessToken) {
      return null;
    }

    const payload = decodeJwtPayload(this.secondaryAccessToken);
    const blocked = findBlockingSecurityFlags(scopeClaimToList(payload?.['scope']));
    if (!blocked.length) {
      return null;
    }

    return {
      status: 'access_denied',
      permissions: [],
      message: securityFlagDenialMessage(blocked),
    };
  }

  private async requestResourceToken(resource: string): Promise<ResourceTokenResponse> {
    const refreshToken = await this.logtoOAuth.getStoredRefreshToken();
    if (!refreshToken) {
      throw new Error('Your KumpeCloud session expired. Sign out and sign in again.');
    }

    const tokenEndpoint = new URL('/oidc/token', environment.logto.endpoint).href;

    const response = await fetchTokenByRefreshToken(
      {
        clientId: environment.logto.appId,
        tokenEndpoint,
        refreshToken,
        resource: normalizeLogtoResource(resource),
      },
      async <T>(url: URL | RequestInfo, init?: RequestInit): Promise<T> => {
        const res = await fetch(url, init);
        const body = await res.text();
        if (!res.ok) {
          console.error(
            `KumpeCloud token request failed (${res.status}) for resource ${resource}:`,
            body,
          );
          throw new Error(parseLogtoTokenError(body || `Token request failed (${res.status})`));
        }
        return JSON.parse(body) as T;
      },
    );

    return {
      accessToken: response.accessToken,
      refreshToken: response.refreshToken,
    };
  }
}
