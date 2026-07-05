import { Component, OnInit, inject } from '@angular/core';
import { Router } from '@angular/router';
import { combineLatest, filter, take, timeout } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import { AuthFlowService } from '../../../core/services/auth-flow.service';
import { AuthStatusComponent } from '../auth-status/auth-status.component';

@Component({
  selector: 'app-callback',
  standalone: true,
  imports: [AuthStatusComponent],
  template: '<app-auth-status message="Completing sign-in…" />',
})
export class CallbackComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly authFlow = inject(AuthFlowService);

  ngOnInit(): void {
    // withAppInitializerAuthCheck() exchanges the auth code once at startup — do not
    // call checkAuth() here or Logto returns 400 (invalid_grant / code reused).
    combineLatest([this.auth.session$, this.auth.authReady$]).pipe(
      filter(([session, authReady]) => authReady && session.status !== 'unauthenticated'),
      take(1),
      timeout(30_000),
    ).subscribe({
      next: ([session]) => {
        const destination = this.authFlow.resolveSessionNavigation(
          session,
          this.router.url,
          true,
        );
        if (destination) {
          this.router.navigate([destination]);
          return;
        }

        if (session.status === 'authenticated') {
          this.router.navigate(['/']);
          return;
        }

        this.router.navigate(['/login']);
      },
      error: () => this.router.navigate(['/login']),
    });
  }
}
