import { Component, Input, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { AuthService } from '../../../core/services/auth.service';
import { TimezoneSelectComponent } from '../../../shared/components/timezone-select/timezone-select.component';
import { User } from '../../../core/models/session.model';
import { PROVIDER_ICON_SM } from '../../../shared/utils/provider-icons';

@Component({
  selector: 'app-profile-card',
  standalone: true,
  imports: [CommonModule, FormsModule, TimezoneSelectComponent],
  templateUrl: './profile-card.component.html',
  styleUrls: ['./profile-card.component.scss'],
})
export class ProfileCardComponent implements OnChanges {
  @Input() user!: User;

  editing = false;
  displayName = '';
  timezone = '';
  saving = false;
  error = '';
  success = '';

  constructor(private auth: AuthService, private sanitizer: DomSanitizer) {}

  providerIcon(name: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(PROVIDER_ICON_SM[name] ?? PROVIDER_ICON_SM['custom_oidc']);
  }

  providerLabel(name: string): string {
    const labels: Record<string, string> = {
      google: 'Google', github: 'GitHub', facebook: 'Facebook',
      apple: 'Apple', microsoft_login: 'Microsoft', microsoft_entra: 'Microsoft Entra',
      custom_oidc: 'Custom OIDC', dev_email: 'Dev Email',
    };
    return labels[name] ?? name;
  }

  ngOnChanges(): void {
    this.displayName = this.user?.display_name ?? '';
    this.timezone = this.user?.timezone ?? 'UTC';
  }

  startEdit(): void {
    this.editing = true;
    this.error = '';
    this.success = '';
  }

  cancel(): void {
    this.editing = false;
    this.ngOnChanges();
  }

  save(): void {
    this.saving = true;
    this.error = '';
    this.auth.updateProfile(this.displayName.trim(), this.timezone).subscribe({
      next: () => {
        this.auth.loadSession().subscribe();
        this.saving = false;
        this.editing = false;
        this.success = 'Profile updated';
        setTimeout(() => (this.success = ''), 3000);
      },
      error: (e: Error) => {
        this.error = e.message;
        this.saving = false;
      },
    });
  }
}
