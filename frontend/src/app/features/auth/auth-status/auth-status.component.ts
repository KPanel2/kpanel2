import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-auth-status',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="auth-shell">
      <div class="auth-card">
        <div class="hero">
          <img class="logo-img" src="logo.webp" alt="kPanel" />
          <span class="logo-text">kPanel</span>
          <p class="tagline">{{ message }}</p>
        </div>
        <div class="auth-spinner" role="status" [attr.aria-label]="message"></div>
      </div>
    </div>
  `,
  styleUrls: ['./auth-status.component.scss'],
})
export class AuthStatusComponent {
  @Input() message = 'Checking sign-in…';
}
