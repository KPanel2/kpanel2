import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { AuthService } from '../../../core/services/auth.service';
import { TimezoneSelectComponent } from '../../../shared/components/timezone-select/timezone-select.component';
import { SessionState, Provider } from '../../../core/models/session.model';
import { TIMEZONES } from '../../../shared/constants/timezones';
import { PROVIDER_ICON_LG } from '../../../shared/utils/provider-icons';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, TimezoneSelectComponent],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent implements OnInit {
  session: SessionState | null = null;
  loading = false;
  error = '';

  // Create account form
  displayName = '';
  timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

  constructor(private auth: AuthService, private router: Router, private sanitizer: DomSanitizer) {}

  ngOnInit(): void {
    this.auth.session$.subscribe(s => {
      this.session = s;
      if (s?.status === 'authenticated') {
        this.router.navigate(['/']);
      }
    });
  }

  // Dev email login
  devEmail = '';

  get providers(): Provider[] {
    return this.session?.providers ?? [];
  }

  get oauthProviders(): Provider[] {
    return this.providers.filter(p => p.name !== 'dev_email');
  }

  providerIcon(name: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(PROVIDER_ICON_LG[name] ?? PROVIDER_ICON_LG['custom_oidc']);
  }

  get hasDevLogin(): boolean {
    return this.providers.some(p => p.name === 'dev_email');
  }

  get status(): string {
    return this.session?.status ?? 'unauthenticated';
  }

  loginWith(provider: string): void {
    window.location.href = `/api/v1/auth/login/${provider}`;
  }

  devLogin(): void {
    if (!this.devEmail.trim()) return;
    window.location.href = `/api/v1/auth/dev-login?email=${encodeURIComponent(this.devEmail.trim())}`;
  }

  createAccount(): void {
    if (!this.displayName.trim() || !this.timezone) return;
    this.loading = true;
    this.error = '';
    this.auth.createAccount(this.displayName.trim(), this.timezone).subscribe({
      next: () => {
        this.auth.loadSession().subscribe();
      },
      error: (e: Error) => {
        this.error = e.message;
        this.loading = false;
      },
    });
  }

  completeLink(): void {
    this.loading = true;
    this.error = '';
    this.auth.completeLink().subscribe({
      next: () => {
        this.auth.loadSession().subscribe();
      },
      error: (e: Error) => {
        this.error = e.message;
        this.loading = false;
      },
    });
  }

  cancelLink(): void {
    this.auth.logout().subscribe({
      next: () => this.auth.loadSession().subscribe(),
    });
  }
}
