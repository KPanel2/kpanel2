import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { AuthDebugPanelComponent } from '../auth-debug-panel/auth-debug-panel.component';
import { TimezoneSelectComponent } from '../../../shared/components/timezone-select/timezone-select.component';
import { SessionState } from '../../../core/models/session.model';
import { environment, isOidcConfigured } from '../../../../environments/environment';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, TimezoneSelectComponent, AuthDebugPanelComponent],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent implements OnInit {
  session: SessionState = { status: 'unauthenticated', permissions: [] };
  loading = false;
  loggingOut = false;
  error = '';
  devEmail = '';

  displayName = '';
  timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

  constructor(private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
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
    if (!this.displayName.trim() || !this.timezone) return;
    this.loading = true;
    this.error = '';
    this.auth.createAccount(this.displayName.trim(), this.timezone).subscribe({
      next: () => this.auth.loadSession().subscribe(),
      error: (e: Error) => {
        this.error = e.message;
        this.loading = false;
      },
    });
  }
}
