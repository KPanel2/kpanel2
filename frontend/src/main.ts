import { bootstrapApplication } from '@angular/platform-browser';

import { createAppConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { environment } from './environments/environment';

async function loadAuthConfig(): Promise<void> {
  const origin = window.location.origin;
  environment.logto.redirectUri = `${origin}/callback`;
  environment.logto.postLogoutRedirectUri = `${origin}/login`;

  const response = await fetch('/api/v1/auth/config');
  if (response.ok) {
    const data = await response.json() as {
      logtoEndpoint?: string;
      appId?: string;
      apiResource?: string;
      secondaryApiResource?: string;
      devAuthEnabled?: boolean;
      authDebugEnabled?: boolean;
    };
    if (data.logtoEndpoint) environment.logto.endpoint = data.logtoEndpoint;
    if (data.appId) environment.logto.appId = data.appId;
    if (data.apiResource) environment.logto.apiResource = data.apiResource;
    if (data.secondaryApiResource) environment.logto.secondaryApiResource = data.secondaryApiResource;
    if (typeof data.devAuthEnabled === 'boolean') environment.devAuthEnabled = data.devAuthEnabled;
    if (typeof data.authDebugEnabled === 'boolean') environment.authDebugEnabled = data.authDebugEnabled;
  }

  const permissionsResponse = await fetch('/api/v1/auth/permissions');
  if (permissionsResponse.ok) {
    const data = await permissionsResponse.json() as {
      permissions?: string[];
      secondaryPermissions?: string[];
    };
    environment.logto.apiPermissions = data.permissions ?? [];
    environment.logto.secondaryPermissions = data.secondaryPermissions ?? [];
  }
}

loadAuthConfig()
  .then(() => bootstrapApplication(AppComponent, createAppConfig()))
  .catch(err => console.error(err));
