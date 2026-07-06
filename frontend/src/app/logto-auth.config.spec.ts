import { UserScope } from '@logto/js';

import { buildAngularAuthConfig, buildSignInScopeList } from './logto-auth.config';

describe('logto-auth.config', () => {
  describe('buildSignInScopeList', () => {
    it('includes reserved user scopes and API permissions', () => {
      const scopes = buildSignInScopeList(['kpanel:admin', 'securityflags:read']);
      expect(scopes).toContain(UserScope.Email);
      expect(scopes).toContain(UserScope.Profile);
      expect(scopes).toContain('kpanel:admin');
      expect(scopes).toContain('securityflags:read');
    });

    it('defaults to reserved scopes only', () => {
      const scopes = buildSignInScopeList();
      expect(scopes.length).toBeGreaterThan(0);
      expect(scopes).toContain(UserScope.Roles);
    });
  });

  describe('buildAngularAuthConfig', () => {
    it('builds OIDC configuration from Logto settings', () => {
      const config = buildAngularAuthConfig({
        endpoint: 'https://auth.example.com',
        appId: 'app-123',
        apiPermissionScopes: ['kpanel:admin'],
        redirectUri: 'http://localhost:8080/callback',
        postLogoutRedirectUri: 'http://localhost:8080/signed-out',
      });

      expect(config.authority).toBe('https://auth.example.com/oidc');
      expect(config.clientId).toBe('app-123');
      expect(config.redirectUrl).toBe('http://localhost:8080/callback');
      expect(config.postLogoutRedirectUri).toBe('http://localhost:8080/signed-out');
      expect(config.responseType).toBe('code');
      expect(config.useRefreshToken).toBeTrue();
      expect(config.scope).toContain('kpanel:admin');
    });
  });
});
