import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { combineLatest } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import {
  AuthFlowService,
  LoginViewContext,
  LoginViewPhase,
} from '../../../core/services/auth-flow.service';
import { SessionState } from '../../../core/models/session.model';
import { environment, isOidcConfigured } from '../../../../environments/environment';
import { AuthStatusComponent } from '../auth-status/auth-status.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, AuthStatusComponent],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent implements OnInit {
  session: SessionState = { status: 'unauthenticated', permissions: [] };
  authReady = false;
  viewPhase: LoginViewPhase = 'checking';
  statusMessage = 'Checking sign-in…';
  loading = false;
  loggingOut = false;
  redirecting = false;
  error = '';
  devEmail = '';
  accountCenterProfileUrl = '';

  constructor(
    private auth: AuthService,
    private authFlow: AuthFlowService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    if (isOidcConfigured()) {
      this.accountCenterProfileUrl = this.auth.accountCenterProfileUrl();
    }

    combineLatest([this.auth.session$, this.auth.authReady$]).subscribe(([session, authReady]) => {
      this.session = session;
      this.authReady = authReady;
      this.updateViewPhase();

      if (authReady && session.status === 'authenticated') {
        this.router.navigate(['/']);
        return;
      }

      this.maybeAutoRedirect();
    });
  }

  get oidcConfigured(): boolean {
    return isOidcConfigured();
  }

  get devAuthEnabled(): boolean {
    return environment.devAuthEnabled;
  }

  signIn(): void {
    this.beginOidcRedirect();
  }

  retrySignIn(): void {
    this.error = '';
    this.beginOidcRedirect();
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

  private viewContext(): LoginViewContext {
    return {
      authReady: this.authReady,
      session: this.session,
      oidcConfigured: this.oidcConfigured,
      devAuthEnabled: this.devAuthEnabled,
      redirecting: this.redirecting,
      redirectError: this.error,
    };
  }

  private updateViewPhase(): void {
    this.viewPhase = this.authFlow.resolveLoginViewPhase(this.viewContext());
    this.statusMessage = this.authFlow.loginStatusMessage(this.viewPhase);
  }

  private maybeAutoRedirect(): void {
    if (!this.authFlow.shouldAutoRedirectToOidc(this.viewContext())) {
      return;
    }

    this.beginOidcRedirect();
  }

  private beginOidcRedirect(): void {
    if (this.redirecting) {
      return;
    }

    this.redirecting = true;
    this.updateViewPhase();
    this.auth.signIn().catch((err: unknown) => {
      this.redirecting = false;
      this.error = err instanceof Error ? err.message : 'Sign-in is not available.';
      this.updateViewPhase();
    });
  }
}
