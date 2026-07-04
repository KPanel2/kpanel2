import { Injectable, Injector, inject } from '@angular/core';
import { OidcSecurityService } from 'angular-auth-oidc-client';

import { isOidcConfigured } from '../../../environments/environment';

/**
 * Lazily resolves OidcSecurityService only when OIDC is configured and provideAuth() ran.
 * Do not inject OidcSecurityService directly — optional inject still constructs the root
 * service and fails when StsConfigLoader was never registered.
 */
@Injectable({ providedIn: 'root' })
export class OidcRuntimeService {
  private readonly injector = inject(Injector);
  private cached: OidcSecurityService | null | undefined;

  get available(): boolean {
    return isOidcConfigured();
  }

  getService(): OidcSecurityService | null {
    if (!isOidcConfigured()) {
      return null;
    }
    if (this.cached !== undefined) {
      return this.cached;
    }
    try {
      this.cached = this.injector.get(OidcSecurityService);
    } catch {
      this.cached = null;
    }
    return this.cached;
  }
}
