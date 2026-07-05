import { Prompt, UserScope, withReservedScopes } from '@logto/js';
import { type OpenIdConfiguration } from 'angular-auth-oidc-client';

export type LogtoAngularConfig = {
  endpoint: string;
  appId: string;
  /** kpanel:* and securityflags:* API permission names (requested at sign-in for refresh token). */
  apiPermissionScopes?: string[];
  redirectUri: string;
  postLogoutRedirectUri?: string;
};

/**
 * OIDC user scopes + API permission names for sign-in consent.
 *
 * API permissions (kpanel:*, securityflags:*) are included here so Logto grants them
 * on the registered resources during login. Per-resource access tokens are fetched
 * afterward with only the resource indicator — not explicit scope lists.
 */
export function buildSignInScopeList(apiPermissionScopes: string[] = []): string[] {
  return withReservedScopes([
    UserScope.Email,
    UserScope.Profile,
    UserScope.CustomData,
    UserScope.Roles,
    ...apiPermissionScopes,
  ]).split(' ').filter(Boolean);
}

/**
 * angular-auth-oidc-client config for session storage and checkAuth on non-callback routes.
 * Sign-in and callback token exchange are handled by LogtoOAuthService (multi-resource).
 */
export function buildAngularAuthConfig(logtoConfig: LogtoAngularConfig): OpenIdConfiguration {
  const {
    endpoint,
    appId: clientId,
    apiPermissionScopes,
    redirectUri: redirectUrl,
    postLogoutRedirectUri,
  } = logtoConfig;

  const scope = buildSignInScopeList(apiPermissionScopes).join(' ');

  return {
    authority: new URL('/oidc', endpoint).href,
    redirectUrl,
    postLogoutRedirectUri,
    clientId,
    scope,
    responseType: 'code',
    autoUserInfo: true,
    renewUserInfoAfterTokenRenew: true,
    silentRenew: false,
    useRefreshToken: true,
    ignoreNonceAfterRefresh: true,
    triggerRefreshWhenIdTokenExpired: false,
    customParamsAuthRequest: {
      prompt: Prompt.Consent,
    },
  };
}
