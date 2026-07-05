export const environment = {
  production: false,
  devAuthEnabled: false,
  logto: {
    endpoint: 'https://auth.stage.kumpe.app',
    appId: '',
    redirectUri: 'http://localhost:8080/callback',
    postLogoutRedirectUri: 'http://localhost:8080/login',
    apiResource: 'http://localhost:8080',
    secondaryApiResource: 'https://securityflags.kumpeapps.com',
    organizationId: '' as string,
    apiPermissions: [] as string[],
    secondaryPermissions: [] as string[],
    elevatedPermissions: [] as string[],
  },
  backendUrl: '',
};

export function isOidcConfigured(): boolean {
  return environment.logto.appId.trim().length > 0;
}
