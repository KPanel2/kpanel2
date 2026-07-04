import { Injectable, inject } from '@angular/core';
import { QueryKey, TokenGrantType, generateSignInUri, Prompt } from '@logto/js';
import { firstValueFrom } from 'rxjs';

import { environment, isOidcConfigured } from '../../../environments/environment';
import { buildSignInScopeList } from '../../logto-auth.config';
import { decodeJwtPayload } from '../../utils/jwt-decode';
import { normalizeLogtoResource } from '../../utils/logto-resource';
import { OidcRuntimeService } from './oidc-runtime.service';

const CODE_VERIFIER_CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
export const KPANEL_SIGNIN_RESOURCES_KEY = 'kpanel_signin_resources';

type TokenResponse = {
  access_token?: string;
  refresh_token?: string;
  id_token?: string;
  expires_in?: number;
  scope?: string;
  token_type?: string;
};

function randomString(length: number): string {
  const values = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(values, value => CODE_VERIFIER_CHARSET[value % CODE_VERIFIER_CHARSET.length]).join('');
}

async function sha256Base64Url(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  const bytes = new Uint8Array(digest);
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

@Injectable({ providedIn: 'root' })
export class LogtoOAuthService {
  private readonly oidcRuntime = inject(OidcRuntimeService);

  async initializeAuth(): Promise<void> {
    if (!isOidcConfigured()) {
      return;
    }

    const url = new URL(window.location.href);
    const code = url.searchParams.get('code');
    if (code && url.pathname.endsWith('/callback')) {
      await this.completeAuthorizationCodeFlow(code, url.searchParams.get('state'));
      this.cleanCallbackUrl();
      return;
    }

    const oidc = this.oidcRuntime.getService();
    if (!oidc) {
      return;
    }

    try {
      await firstValueFrom(oidc.checkAuthMultiple());
    } catch {
      // No stored session — user is unauthenticated.
    }
  }

  async startSignIn(): Promise<void> {
    if (!isOidcConfigured()) {
      throw new Error('KumpeCloud sign-in is not configured. Set KPANEL_LOGTO_APP_ID on the backend.');
    }

    const oidc = this.oidcRuntime.getService();
    if (!oidc) {
      throw new Error('KumpeCloud sign-in is not configured. Set KPANEL_LOGTO_APP_ID on the backend.');
    }

    const config = await firstValueFrom(oidc.getConfiguration());
    if (!config) {
      throw new Error('KumpeCloud sign-in is not configured.');
    }

    const configId = config.configId ?? `0-${environment.logto.appId}`;
    await firstValueFrom(oidc.preloadAuthWellKnownDocument());

    const discovery = await fetch(new URL('/oidc/.well-known/openid-configuration', environment.logto.endpoint))
      .then(response => response.json() as Promise<{ authorization_endpoint?: string; token_endpoint?: string }>);

    const authorizationEndpoint = discovery.authorization_endpoint
      ?? new URL('/oidc/auth', environment.logto.endpoint).href;

    const codeVerifier = randomString(67);
    const codeChallenge = await sha256Base64Url(codeVerifier);
    const state = randomString(32);
    const nonce = randomString(32);

    const resources = this.signInResources();
    sessionStorage.setItem(KPANEL_SIGNIN_RESOURCES_KEY, JSON.stringify(resources));

    this.persistOidcState(configId, {
      codeVerifier,
      authStateControl: state,
      authNonce: nonce,
    });

    const scopes = buildSignInScopeList([
      ...environment.logto.apiPermissions,
      ...environment.logto.secondaryPermissions,
    ]);

    const signInUrl = generateSignInUri({
      authorizationEndpoint,
      clientId: environment.logto.appId,
      redirectUri: environment.logto.redirectUri,
      codeChallenge,
      state,
      scopes,
      resources,
      prompt: Prompt.Consent,
      extraParams: { nonce },
      includeReservedScopes: false,
    });

    window.location.assign(signInUrl);
  }

  private signInResources(): string[] {
    return [
      environment.logto.apiResource,
      environment.logto.secondaryApiResource,
    ]
      .filter((resource): resource is string => Boolean(resource?.trim()))
      .map(normalizeLogtoResource);
  }

  private async completeAuthorizationCodeFlow(code: string, state: string | null): Promise<void> {
    const oidc = this.oidcRuntime.getService();
    if (!oidc) {
      throw new Error('KumpeCloud sign-in is not configured.');
    }

    const config = await firstValueFrom(oidc.getConfiguration());
    if (!config) {
      throw new Error('KumpeCloud sign-in is not configured.');
    }

    const configId = config.configId ?? `0-${environment.logto.appId}`;
    const stored = this.readOidcState(configId);
    const codeVerifier = stored['codeVerifier'];
    const expectedState = stored['authStateControl'];
    const expectedNonce = stored['authNonce'];

    if (typeof codeVerifier !== 'string' || !codeVerifier || typeof expectedState !== 'string' || !expectedState || state !== expectedState) {
      throw new Error('Sign-in state expired. Please try again.');
    }

    const discovery = await fetch(new URL('/oidc/.well-known/openid-configuration', environment.logto.endpoint))
      .then(response => response.json() as Promise<{ token_endpoint?: string }>);
    const tokenEndpoint = discovery.token_endpoint
      ?? new URL('/oidc/token', environment.logto.endpoint).href;

    const resources = this.readSignInResources();
    const parameters = new URLSearchParams();
    parameters.append(QueryKey.ClientId, environment.logto.appId);
    parameters.append(QueryKey.Code, code);
    parameters.append(QueryKey.CodeVerifier, codeVerifier);
    parameters.append(QueryKey.RedirectUri, environment.logto.redirectUri);
    parameters.append(QueryKey.GrantType, TokenGrantType.AuthorizationCode);
    for (const resource of resources) {
      parameters.append(QueryKey.Resource, resource);
    }

    const response = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: parameters.toString(),
    });
    const body = await response.text();
    if (!response.ok) {
      console.error('KumpeCloud authorization code exchange failed:', body);
      throw new Error('KumpeCloud sign-in failed during token exchange.');
    }

    const tokenResponse = JSON.parse(body) as TokenResponse;
    if (!tokenResponse.access_token || !tokenResponse.id_token || !tokenResponse.refresh_token) {
      throw new Error('KumpeCloud sign-in returned an incomplete token response.');
    }

    const payload = decodeJwtPayload(tokenResponse.id_token);
    const nonce = payload?.['nonce'];
    if (typeof expectedNonce !== 'string' || typeof nonce !== 'string' || nonce !== expectedNonce) {
      throw new Error('KumpeCloud sign-in failed nonce validation.');
    }

    const expiresAt = tokenResponse.expires_in
      ? Date.now() + tokenResponse.expires_in * 1000
      : undefined;

    this.persistOidcState(configId, {
      ...stored,
      authnResult: {
        access_token: tokenResponse.access_token,
        refresh_token: tokenResponse.refresh_token,
        id_token: tokenResponse.id_token,
        expires_in: tokenResponse.expires_in,
        scope: tokenResponse.scope,
        token_type: tokenResponse.token_type,
        state: expectedState,
      },
      authzData: tokenResponse.access_token,
      ...(expiresAt ? { access_token_expires_at: expiresAt } : {}),
      authStateControl: '',
      authNonce: null,
    });
    sessionStorage.removeItem(KPANEL_SIGNIN_RESOURCES_KEY);
  }

  private readSignInResources(): string[] {
    const raw = sessionStorage.getItem(KPANEL_SIGNIN_RESOURCES_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as unknown;
        if (Array.isArray(parsed) && parsed.every(item => typeof item === 'string')) {
          return parsed.map(normalizeLogtoResource);
        }
      } catch {
        // fall through to configured defaults
      }
    }
    return this.signInResources();
  }

  async getStoredRefreshToken(): Promise<string | null> {
    const oidc = this.oidcRuntime.getService();
    if (!oidc) {
      return null;
    }
    return firstValueFrom(oidc.getRefreshToken());
  }

  async updateStoredRefreshToken(refreshToken: string): Promise<void> {
    const oidc = this.oidcRuntime.getService();
    if (!oidc) {
      return;
    }

    const config = await firstValueFrom(oidc.getConfiguration());
    if (!config) {
      return;
    }

    const configId = config.configId ?? `0-${environment.logto.appId}`;
    const stored = this.readOidcState(configId);
    const authnResult = stored['authnResult'];
    if (!authnResult || typeof authnResult !== 'object') {
      return;
    }

    this.persistOidcState(configId, {
      ...stored,
      authnResult: {
        ...(authnResult as Record<string, unknown>),
        refresh_token: refreshToken,
      },
    });
  }

  private readOidcState(configId: string): Record<string, unknown> {
    const raw = sessionStorage.getItem(configId);
    if (!raw) {
      return {};
    }
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return {};
    }
  }

  private persistOidcState(configId: string, values: Record<string, unknown>): void {
    const stored = this.readOidcState(configId);
    Object.assign(stored, values);
    sessionStorage.setItem(configId, JSON.stringify(stored));
  }

  private cleanCallbackUrl(): void {
    const url = new URL(window.location.href);
    url.search = '';
    window.history.replaceState({}, document.title, `${url.pathname}${url.hash}`);
  }
}
