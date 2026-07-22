import { Component, EventEmitter, Input, OnChanges, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { AuthService } from '../../../core/services/auth.service';
import { User } from '../../../core/models/session.model';
import { PROVIDER_ICON_SM } from '../../../shared/utils/provider-icons';
import { isOidcConfigured } from '../../../../environments/environment';

const ACCOUNT_CENTER_SUCCESS_MESSAGES: Record<string, string> = {
  profile: 'Profile updated in KumpeCloud Auth.',
  email: 'Email updated in KumpeCloud Auth.',
  password: 'Password updated in KumpeCloud Auth.',
  username: 'Username updated in KumpeCloud Auth.',
  security: 'Security settings updated in KumpeCloud Auth.',
};

@Component({
  selector: 'app-profile-card',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './profile-card.component.html',
  styleUrls: ['./profile-card.component.scss'],
})
export class ProfileCardComponent implements OnChanges, OnInit {
  @Input() user!: User;
  @Output() changed = new EventEmitter<void>();

  success = '';
  error = '';
  accountCenterAvailable = false;
  profileManageUrl = '';
  emailManageUrl = '';
  securityManageUrl = '';

  haBootstrapUrl = '';
  haBindingSecret = '';
  clearHaBinding = false;
  savingHa = false;

  constructor(private auth: AuthService, private sanitizer: DomSanitizer) {}

  ngOnInit(): void {
    this.accountCenterAvailable = isOidcConfigured();
    if (this.accountCenterAvailable) {
      this.profileManageUrl = this.auth.accountCenterProfileUrl();
      this.emailManageUrl = this.auth.accountCenterEmailUrl();
      this.securityManageUrl = this.auth.accountCenterSecurityUrl();
    }

    const successKey = this.auth.takeAccountCenterSuccessKey();
    if (successKey) {
      this.success = ACCOUNT_CENTER_SUCCESS_MESSAGES[successKey]
        ?? 'Account settings updated in KumpeCloud Auth.';
      setTimeout(() => (this.success = ''), 5000);
    }
  }

  providerIcon(name: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(PROVIDER_ICON_SM[name] ?? PROVIDER_ICON_SM['custom_oidc']);
  }

  providerLabel(name: string): string {
    const labels: Record<string, string> = {
      google: 'Google', github: 'GitHub', facebook: 'Facebook',
      apple: 'Apple', microsoft_login: 'Microsoft', microsoft_entra: 'Microsoft Entra',
      custom_oidc: 'Custom OIDC', dev_email: 'Dev Email', kumpecloud: 'KumpeCloud',
    };
    return labels[name] ?? name;
  }

  ngOnChanges(): void {
    this.haBootstrapUrl = this.user?.ha_bootstrap_url ?? '';
    this.haBindingSecret = '';
    this.clearHaBinding = false;
  }

  saveHaBinding(): void {
    this.savingHa = true;
    this.error = '';
    if (this.clearHaBinding) {
      this.auth.updateHaBinding({ clear_ha_binding: true }).subscribe({
        next: () => this.onHaSaved(),
        error: (e: Error) => this.onHaError(e),
      });
      return;
    }

    const bootstrap = this.haBootstrapUrl.trim();
    const secret = this.haBindingSecret.trim();
    if (!bootstrap && !secret) {
      this.savingHa = false;
      this.error = 'Enter a bootstrap URL and/or binding secret, or clear the binding.';
      return;
    }

    this.auth.updateHaBinding({
      ...(bootstrap ? { ha_bootstrap_url: bootstrap } : {}),
      ...(secret ? { ha_binding_secret: secret } : {}),
    }).subscribe({
      next: () => this.onHaSaved(),
      error: (e: Error) => this.onHaError(e),
    });
  }

  private onHaSaved(): void {
    this.savingHa = false;
    this.haBindingSecret = '';
    this.clearHaBinding = false;
    this.success = 'HA binding saved';
    setTimeout(() => (this.success = ''), 3000);
    this.changed.emit();
  }

  private onHaError(e: Error): void {
    this.savingHa = false;
    this.error = e.message;
  }
}
