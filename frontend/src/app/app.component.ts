import { Component, OnInit, inject } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { switchMap, take } from 'rxjs';

import { AuthService } from './core/services/auth.service';
import { OidcRuntimeService } from './core/services/oidc-runtime.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class AppComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly oidcRuntime = inject(OidcRuntimeService);

  ngOnInit(): void {
    this.auth.session$.subscribe(session => this.handleSession(session));

    const accountCenterSuccess = this.auth.consumeAccountCenterSuccess();
    const refreshClaims = accountCenterSuccess;

    const oidc = this.oidcRuntime.getService();
    const bootstrap$ = oidc
      ? oidc.isAuthenticated().pipe(
        take(1),
        switchMap(isAuthenticated => (
          isAuthenticated
            ? this.auth.bootstrapAfterLogin({ refreshClaims })
            : this.auth.loadSession({ refreshClaims })
        )),
      )
      : this.auth.loadSession({ refreshClaims });

    bootstrap$.subscribe({
      error: () => {
        if (!this.router.url.startsWith('/callback')) {
          this.router.navigate(['/login']);
        }
      },
    });
  }

  private handleSession(session: { status: string }): void {
    if (session.status === 'authenticated' && this.router.url.startsWith('/login')) {
      this.router.navigate(['/']);
    } else if (session.status === 'access_denied' && !this.router.url.startsWith('/login')) {
      this.router.navigate(['/login']);
    } else if (
      session.status === 'unauthenticated'
      && !this.router.url.startsWith('/login')
      && !this.router.url.startsWith('/callback')
    ) {
      this.router.navigate(['/login']);
    }
  }
}
