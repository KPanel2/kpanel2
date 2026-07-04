import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import {
  AuthDebugService,
  AuthDebugSnapshot,
  KPANEL_AUTH_DEBUG_KEY,
} from '../../../core/services/auth-debug.service';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-auth-debug-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <details class="auth-debug" *ngIf="enabled" [open]="openByDefault">
      <summary>Auth debug (dev)</summary>
      <p class="hint">
        Stored in <code>sessionStorage['{{ storageKey }}']</code>.
        Check <strong>delivery.securityFlagsHeaderSent</strong> on the session request and <strong>serverDebug.wouldDeny</strong>.
      </p>
      <div class="actions">
        <button type="button" class="btn-ghost" (click)="refresh()">Refresh</button>
        <button type="button" class="btn-ghost" (click)="copy()">Copy JSON</button>
      </div>
      <pre *ngIf="snapshot as data">{{ data | json }}</pre>
      <p *ngIf="!snapshot" class="empty">No auth debug snapshot yet — sign in and load session.</p>
    </details>
  `,
  styles: [`
    .auth-debug {
      margin: 1rem 0;
      padding: 0.75rem 1rem;
      border: 1px dashed #c9a227;
      border-radius: 8px;
      background: #fffbea;
      color: #3d3500;
      font-size: 0.85rem;
    }

    summary {
      cursor: pointer;
      font-weight: 600;
    }

    .hint {
      margin: 0.5rem 0;
      opacity: 0.9;
    }

    .actions {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
    }

    pre {
      margin: 0;
      max-height: 28rem;
      overflow: auto;
      padding: 0.75rem;
      background: #1e1e1e;
      color: #d4d4d4;
      border-radius: 6px;
      font-size: 0.75rem;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .empty {
      margin: 0.5rem 0 0;
      font-style: italic;
    }
  `],
})
export class AuthDebugPanelComponent implements OnInit {
  readonly storageKey = KPANEL_AUTH_DEBUG_KEY;
  enabled = false;
  openByDefault = false;
  snapshot: AuthDebugSnapshot | null = null;

  constructor(private authDebug: AuthDebugService) {}

  ngOnInit(): void {
    this.enabled = environment.authDebugEnabled || !environment.production;
    this.refresh();
    this.openByDefault = this.snapshot?.sessionStatus === 'access_denied'
      || (this.snapshot?.tokens.securityFlagsToken.scope.length ?? 0) > 0;
  }

  refresh(): void {
    this.snapshot = this.authDebug.readSnapshot();
  }

  copy(): void {
    const raw = sessionStorage.getItem(this.storageKey);
    if (!raw) {
      return;
    }
    void navigator.clipboard.writeText(raw);
  }
}
