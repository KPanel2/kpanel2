import { Injectable } from '@angular/core';

import { environment } from '../../../environments/environment';

export type AccountCenterPage =
  | 'profile'
  | 'security'
  | 'email'
  | 'password'
  | 'username';

export type AccountCenterLinkOptions = {
  /** When true, Logto appends show_success to the redirect URL after the user completes the action. */
  showSuccess?: boolean;
  /** Override the post-action redirect target (defaults to the current page URL without query params). */
  redirectUrl?: string;
};

/**
 * Builds URLs for KumpeCloud Auth's prebuilt Account Center UI.
 * @see https://docs.logto.io/end-user-flows/account-settings/by-account-center-ui
 */
@Injectable({ providedIn: 'root' })
export class KumpeAccountCenterService {
  profileUrl(options: AccountCenterLinkOptions = {}): string {
    return this.buildUrl('/account/profile', options);
  }

  securityUrl(options: AccountCenterLinkOptions = {}): string {
    return this.buildUrl('/account/security', options);
  }

  emailUrl(options: AccountCenterLinkOptions = {}): string {
    return this.buildUrl('/account/email', options);
  }

  passwordUrl(options: AccountCenterLinkOptions = {}): string {
    return this.buildUrl('/account/password', options);
  }

  usernameUrl(options: AccountCenterLinkOptions = {}): string {
    return this.buildUrl('/account/username', options);
  }

  buildUrl(path: string, options: AccountCenterLinkOptions = {}): string {
    const endpoint = environment.logto.endpoint.replace(/\/+$/, '');
    const url = new URL(path.startsWith('/') ? path : `/${path}`, `${endpoint}/`);
    const redirectTarget = options.redirectUrl ?? this.defaultRedirectUrl();
    url.searchParams.set('redirect', redirectTarget);
    if (options.showSuccess) {
      url.searchParams.set('show_success', 'true');
    }
    return url.href;
  }

  private defaultRedirectUrl(): string {
    const current = new URL(window.location.href);
    current.search = '';
    current.hash = '';
    return current.href;
  }
}
