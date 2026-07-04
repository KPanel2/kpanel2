import { Component, OnInit, inject } from '@angular/core';
import { Router } from '@angular/router';
import { filter, take, timeout } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-callback',
  standalone: true,
  template: '<p class="status">Completing sign-in…</p>',
  styles: ['.status { padding: 2rem; text-align: center; color: #64748b; }'],
})
export class CallbackComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);

  ngOnInit(): void {
    // withAppInitializerAuthCheck() exchanges the auth code once at startup — do not
    // call checkAuth() here or Logto returns 400 (invalid_grant / code reused).
    this.auth.session$.pipe(
      filter(session => session.status !== 'unauthenticated'),
      take(1),
      timeout(30_000),
    ).subscribe({
      next: session => {
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
