import { Component, OnInit, inject } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';

import { AuthService } from './core/services/auth.service';
import { AuthFlowService } from './core/services/auth-flow.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class AppComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly authFlow = inject(AuthFlowService);
  private readonly router = inject(Router);

  ngOnInit(): void {
    this.auth.session$.subscribe(session => {
      const destination = this.authFlow.resolveSessionNavigation(
        session,
        this.router.url,
        this.auth.authReady,
      );
      if (destination) {
        this.router.navigate([destination]);
      }
    });

    const refreshClaims = this.auth.consumeAccountCenterSuccess();

    this.auth.bootstrapApp({ refreshClaims }).subscribe({
      error: () => {
        if (!this.router.url.startsWith('/callback')) {
          this.router.navigate(['/login']);
        }
      },
    });
  }
}
