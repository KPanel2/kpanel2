import { Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DeviceService } from '../../../core/services/device.service';

@Component({
  selector: 'app-claim-device',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './claim-device.component.html',
})
export class ClaimDeviceComponent {
  @Output() claimed = new EventEmitter<void>();

  code = '';
  loading = false;
  error = '';
  success = '';

  constructor(private deviceService: DeviceService) {}

  claim(): void {
    const trimmed = this.code.trim();
    if (!trimmed) return;
    this.loading = true;
    this.error = '';
    this.success = '';
    this.deviceService.claimDevice(trimmed).subscribe({
      next: () => {
        this.code = '';
        this.success = 'Device claimed successfully';
        this.loading = false;
        this.claimed.emit();
        setTimeout(() => (this.success = ''), 3000);
      },
      error: (e: Error) => {
        this.error = e.message;
        this.loading = false;
      },
    });
  }
}
