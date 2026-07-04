import { ApplicationConfig, inject, provideAppInitializer, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { provideAuth } from 'angular-auth-oidc-client';

import { routes } from './app.routes';
import { environment, isOidcConfigured } from '../environments/environment';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { LogtoOAuthService } from './core/services/logto-oauth.service';
import { buildAngularAuthConfig } from './logto-auth.config';

export function createAppConfig(): ApplicationConfig {
  const providers = [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withFetch(), withInterceptors([authInterceptor])),
  ];

  if (isOidcConfigured()) {
    const logtoConfig = buildAngularAuthConfig({
      endpoint: environment.logto.endpoint,
      appId: environment.logto.appId,
      redirectUri: environment.logto.redirectUri,
      postLogoutRedirectUri: environment.logto.postLogoutRedirectUri,
      apiPermissionScopes: [
        ...environment.logto.apiPermissions,
        ...environment.logto.secondaryPermissions,
      ],
    });
    providers.push(
      provideAuth({ config: logtoConfig }),
      provideAppInitializer(() => {
        const logtoOAuth = inject(LogtoOAuthService);
        return logtoOAuth.initializeAuth();
      }),
    );
  }

  return { providers };
}

export const appConfig = createAppConfig();
