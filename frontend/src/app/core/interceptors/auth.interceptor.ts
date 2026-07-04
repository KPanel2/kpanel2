import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { switchMap, take } from 'rxjs';

import { AuthRequestTraceService } from '../services/auth-request-trace.service';
import { LogtoApiTokenService } from '../services/logto-api-token.service';
import { OidcRuntimeService } from '../services/oidc-runtime.service';

function isKpanelApiRequest(url: string): boolean {
  if (url.startsWith('/api/')) {
    return true;
  }

  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.origin === window.location.origin && parsed.pathname.startsWith('/api/');
  } catch {
    return false;
  }
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!isKpanelApiRequest(req.url)) {
    return next(req);
  }

  const apiTokenService = inject(LogtoApiTokenService);
  const requestTrace = inject(AuthRequestTraceService);
  const oidc = inject(OidcRuntimeService).getService();

  const send = (idToken: string | null | undefined) => {
    const headers: Record<string, string> = {};
    const apiToken = apiTokenService.token;
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }
    if (idToken?.trim()) {
      headers['X-Id-Token'] = idToken;
    }
    const securityToken = apiTokenService.secondaryToken;
    if (securityToken) {
      headers['X-SecurityFlags-Token'] = securityToken;
    }

    requestTrace.record({
      authorization: Boolean(apiToken),
      idToken: Boolean(idToken?.trim()),
      securityFlags: Boolean(securityToken),
    });

    return next(req.clone({ setHeaders: headers }));
  };

  if (!oidc) {
    return send(null);
  }

  return oidc.getIdToken().pipe(
    take(1),
    switchMap(idToken => send(idToken)),
  );
};
