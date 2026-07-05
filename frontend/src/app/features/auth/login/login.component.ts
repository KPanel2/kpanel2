import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { AuthDebugPanelComponent } from '../auth-debug-panel/auth-debug-panel.component';
import { SessionState } from '../../../core/models/session.model';
import { environment, isOidcConfigured } from '../../../../environments/environment';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, AuthDebugPanelComponent],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent implements OnInit {
  session: SessionState = { status: 'unauthenticated', permissions: [] };
  loading = false;
  loggingOut = false;
  error = '';
  devEmail = '';
  accountCenterProfileUrl = '';

  constructor(private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    if (isOidcConfigured()) {
      this.accountCenterProfileUrl = this.auth.accountCenterProfileUrl();
    }

    this.auth.session$.subscribe(s => {
      this.session = s;
      if (s?.status === 'authenticated') {
        this.router.navigate(['/']);
      }
    });
  }

  get status(): string {
    return this.session.status;
  }

  get oidcConfigured(): boolean {
    return isOidcConfigured();
  }

  get devAuthEnabled(): boolean {
    return environment.devAuthEnabled;
  }

  signIn(): void {
    this.error = '';
    this.auth.signIn().catch((err: unknown) => {
      this.error = err instanceof Error ? err.message : 'Sign-in is not available.';
    });
  }

  logout(): void {
    this.loggingOut = true;
    this.error = '';
    this.auth.logout().subscribe({
      next: () => {
        this.loggingOut = false;
      },
      error: () => {
        this.loggingOut = false;
        this.error = 'Sign out failed. Please try again.';
      },
    });
  }

  devLogin(): void {
    if (!this.devEmail.trim()) return;
    localStorage.setItem('kpanel_dev_email', this.devEmail.trim());
    this.auth.loadSession().subscribe();
  }

  createAccount(): void {
    this.loading = true;
    this.error = '';
    this.auth.createAccount().subscribe({
      next: () => this.auth.loadSession().subscribe(),
      error: (e: Error) => {
        this.error = e.message;
        this.loading = false;
      },
    });
  }
}
