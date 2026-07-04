import { Injectable } from '@angular/core';

export type AuthRequestHeaders = {
  authorization: boolean;
  idToken: boolean;
  securityFlags: boolean;
};

/** Records which auth headers were attached to the most recent kPanel API request. */
@Injectable({ providedIn: 'root' })
export class AuthRequestTraceService {
  private last: AuthRequestHeaders = {
    authorization: false,
    idToken: false,
    securityFlags: false,
  };

  record(headers: AuthRequestHeaders): void {
    this.last = headers;
  }

  snapshot(): AuthRequestHeaders {
    return { ...this.last };
  }

  clear(): void {
    this.last = {
      authorization: false,
      idToken: false,
      securityFlags: false,
    };
  }
}
