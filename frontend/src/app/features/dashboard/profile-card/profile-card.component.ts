import { Component, Input, OnChanges, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
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
  imports: [CommonModule],
  templateUrl: './profile-card.component.html',
  styleUrls: ['./profile-card.component.scss'],
})
export class ProfileCardComponent implements OnChanges, OnInit {
  @Input() user!: User;

  success = '';
  accountCenterAvailable = false;
  profileManageUrl = '';
  emailManageUrl = '';
  securityManageUrl = '';

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
    // user input drives the read-only view
  }
}
