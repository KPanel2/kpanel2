import { Component, EventEmitter, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DeviceService } from '../../../core/services/device.service';
import { HouseholdService } from '../../../core/services/household.service';
import { Household, HouseholdUrl } from '../../../core/models/household.model';

@Component({
  selector: 'app-claim-device',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './claim-device.component.html',
})
export class ClaimDeviceComponent implements OnInit {
  @Output() claimed = new EventEmitter<void>();

  code = '';
  targetUrl = '';
  loading = false;
  error = '';
  success = '';

  households: Household[] = [];
  selectedHouseholdId: number | null = null;

  constructor(
    private deviceService: DeviceService,
    private householdService: HouseholdService,
  ) {}

  ngOnInit(): void {
    this.householdService.listHouseholds().subscribe({
      next: (households) => {
        this.households = households;
        if (households.length === 1) {
          this.selectedHouseholdId = households[0].id;
          this._applyHouseholdDefault(households[0]);
        }
      },
      error: () => {},
    });
  }

  get selectedHousehold(): Household | null {
    return this.households.find(h => h.id === this.selectedHouseholdId) ?? null;
  }

  get defaultHouseholdUrl(): HouseholdUrl | null {
    return this.selectedHousehold?.urls.find(u => u.is_default) ?? null;
  }

  onHouseholdChange(): void {
    const h = this.selectedHousehold;
    if (h) {
      this._applyHouseholdDefault(h);
    } else {
      this.targetUrl = '';
    }
  }

  private _applyHouseholdDefault(h: Household): void {
    const def = h.urls.find(u => u.is_default);
    if (def && !this.targetUrl) {
      this.targetUrl = def.url_template;
    }
  }

  claim(): void {
    const trimmed = this.code.trim();
    if (!trimmed) return;
    this.loading = true;
    this.error = '';
    this.success = '';

    const householdId = this.selectedHouseholdId ?? undefined;
    // Only send targetUrl if it differs from the default (i.e. the user typed a custom one).
    const defaultUrl = this.defaultHouseholdUrl?.url_template ?? '';
    const customUrl = this.targetUrl.trim();
    const urlOverride = customUrl && customUrl !== defaultUrl ? customUrl : undefined;

    this.deviceService.claimDevice(trimmed, householdId, urlOverride).subscribe({
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
