import { Injectable } from '@angular/core';

import { SessionState } from '../models/session.model';

export type LoginViewPhase =
  | 'checking'
  | 'redirecting'
  | 'access_denied'
  | 'needs_account'
  | 'dev_sign_in'
  | 'oidc_fallback'
  | 'unconfigured';

export interface LoginViewContext {
  authReady: boolean;
  session: SessionState;
  oidcConfigured: boolean;
  devAuthEnabled: boolean;
  redirecting: boolean;
  redirectError: string;
}

export function resolveLoginViewPhase(context: LoginViewContext): LoginViewPhase {
  const {
    authReady,
    session,
    oidcConfigured,
    devAuthEnabled,
    redirecting,
    redirectError,
  } = context;

  if (!authReady || session.status === 'authenticated') {
    return 'checking';
  }

  if (redirecting) {
    return 'redirecting';
  }

  if (session.status === 'access_denied') {
    return 'access_denied';
  }

  if (session.status === 'needs_account') {
    return 'needs_account';
  }

  if (redirectError) {
    return 'oidc_fallback';
  }

  if (oidcConfigured) {
    return 'redirecting';
  }

  if (devAuthEnabled) {
    return 'dev_sign_in';
  }

  return 'unconfigured';
}

export function shouldAutoRedirectToOidc(context: LoginViewContext): boolean {
  const { authReady, session, oidcConfigured, redirecting, redirectError } = context;

  if (!authReady || redirecting || redirectError) {
    return false;
  }

  if (session.status !== 'unauthenticated') {
    return false;
  }

  return oidcConfigured;
}

export function resolveSessionNavigation(
  session: SessionState,
  url: string,
  authReady: boolean,
): string | null {
  if (!authReady) {
    return null;
  }

  if (session.status === 'authenticated' && url.startsWith('/login')) {
    return '/';
  }

  if (session.status === 'access_denied' && !url.startsWith('/login')) {
    return '/login';
  }

  if (
    session.status === 'unauthenticated'
    && !url.startsWith('/login')
    && !url.startsWith('/callback')
  ) {
    return '/login';
  }

  return null;
}

export function loginStatusMessage(phase: LoginViewPhase): string {
  switch (phase) {
    case 'checking':
      return 'Checking sign-in…';
    case 'redirecting':
      return 'Redirecting to KumpeCloud…';
    default:
      return '';
  }
}

@Injectable({ providedIn: 'root' })
export class AuthFlowService {
  resolveLoginViewPhase = resolveLoginViewPhase;
  shouldAutoRedirectToOidc = shouldAutoRedirectToOidc;
  resolveSessionNavigation = resolveSessionNavigation;
  loginStatusMessage = loginStatusMessage;
}
