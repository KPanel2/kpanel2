import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DeviceService } from '../../../core/services/device.service';
import { TimezoneSelectComponent } from '../../../shared/components/timezone-select/timezone-select.component';
import { Device } from '../../../core/models/session.model';
import { Household, Room, HouseholdUrl } from '../../../core/models/household.model';
import { TIMEZONES } from '../../../shared/constants/timezones';

@Component({
  selector: 'app-device-card',
  standalone: true,
  imports: [CommonModule, FormsModule, TimezoneSelectComponent],
  templateUrl: './device-card.component.html',
  styleUrls: ['./device-card.component.scss'],
})
export class DeviceCardComponent implements OnChanges {
  @Input() device!: Device;
  @Input() households: Household[] = [];
  @Output() changed = new EventEmitter<void>();

  editing = false;
  showTempUrl = false;

  // Edit form state
  displayName = '';
  targetUrl = '';
  timezone = '';
  roomId: number | null = null;
  selectedHouseholdId: number | null = null;
  urlMode = 'custom';
  householdUrlId: number | null = null;
  tempUrlInput = '';

  saving = false;
  error = '';
  success = '';

  constructor(private deviceService: DeviceService) {}

  ngOnChanges(): void {
    this.displayName = this.device?.display_name ?? '';
    this.targetUrl = this.device?.target_url ?? '';
    this.timezone = this.device?.timezone ?? '';
    this.roomId = this.device?.room_id ?? null;
    this.urlMode = this.device?.url_mode ?? 'custom';
    this.householdUrlId = this.device?.household_url_id ?? null;
    // Infer household from current room assignment
    this.selectedHouseholdId = this.device?.room_id
      ? (this.households.find(h => (h.rooms ?? []).some(r => r.id === this.device.room_id))?.id ?? null)
      : null;
  }

  get allRooms(): Room[] {
    return this.households.flatMap(h => h.rooms ?? []);
  }

  get roomsForHousehold(): Room[] {
    if (this.selectedHouseholdId === null) return this.allRooms;
    return this.households.find(h => h.id === this.selectedHouseholdId)?.rooms ?? [];
  }

  get deviceRoom(): Room | undefined {
    return this.allRooms.find(r => r.id === this.device?.room_id);
  }

  get deviceHousehold(): Household | undefined {
    if (!this.device?.room_id) return undefined;
    return this.households.find(h => (h.rooms ?? []).some(r => r.id === this.device.room_id));
  }

  onHouseholdChange(): void {
    if (this.roomId !== null && this.selectedHouseholdId !== null) {
      const roomBelongs = (this.households.find(h => h.id === this.selectedHouseholdId)?.rooms ?? [])
        .some(r => r.id === this.roomId);
      if (!roomBelongs) this.roomId = null;
    }
  }

  get allHouseholdUrls(): (HouseholdUrl & { householdName: string })[] {
    return this.households.flatMap(h =>
      (h.urls ?? []).map(u => ({ ...u, householdName: h.name }))
    );
  }

  startEdit(): void {
    this.editing = true;
    this.error = '';
    this.success = '';
  }

  cancelEdit(): void {
    this.editing = false;
    this.ngOnChanges();
  }

  saveEdit(): void {
    this.saving = true;
    this.error = '';
    const payload: Record<string, unknown> = {
      display_name: this.displayName.trim() || null,
      timezone: this.timezone || null,
      url_mode: this.urlMode,
    };
    if (this.roomId !== null) {
      payload['room_id'] = this.roomId;
    } else {
      payload['clear_room'] = true;
    }
    if (this.urlMode === 'custom') {
      payload['target_url'] = this.targetUrl.trim() || null;
    } else {
      payload['household_url_id'] = this.householdUrlId;
    }

    this.deviceService.updateDevice(this.device.registration_code, payload).subscribe({
      next: () => {
        this.saving = false;
        this.editing = false;
        this.success = 'Saved';
        this.changed.emit();
        setTimeout(() => (this.success = ''), 3000);
      },
      error: (e: Error) => {
        this.error = e.message;
        this.saving = false;
      },
    });
  }

  delete(): void {
    if (!confirm(`Delete device "${this.device.display_name ?? this.device.registration_code}"?`)) return;
    this.deviceService.deleteDevice(this.device.registration_code).subscribe({
      next: () => this.changed.emit(),
      error: (e: Error) => (this.error = e.message),
    });
  }

  sendAction(action: 'reboot' | 'update'): void {
    this.deviceService.sendAction(this.device.registration_code, action).subscribe({
      next: () => {
        this.success = `${action} command sent`;
        setTimeout(() => (this.success = ''), 3000);
      },
      error: (e: Error) => (this.error = e.message),
    });
  }

  setTempUrl(): void {
    if (!this.tempUrlInput.trim()) return;
    this.saving = true;
    this.deviceService.setTempUrl(this.device.registration_code, this.tempUrlInput.trim()).subscribe({
      next: () => {
        this.saving = false;
        this.showTempUrl = false;
        this.tempUrlInput = '';
        this.success = 'Temp URL set';
        this.changed.emit();
        setTimeout(() => (this.success = ''), 3000);
      },
      error: (e: Error) => {
        this.error = e.message;
        this.saving = false;
      },
    });
  }

  clearTempUrl(): void {
    this.deviceService.clearTempUrl(this.device.registration_code).subscribe({
      next: () => {
        this.success = 'Temp URL cleared';
        this.changed.emit();
        setTimeout(() => (this.success = ''), 3000);
      },
      error: (e: Error) => (this.error = e.message),
    });
  }
}
