import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HouseholdService } from '../../../core/services/household.service';
import { AuthService } from '../../../core/services/auth.service';
import { TimezoneSelectComponent } from '../../../shared/components/timezone-select/timezone-select.component';
import { FloorManagerComponent } from '../floor-manager/floor-manager.component';
import { RoomManagerComponent } from '../room-manager/room-manager.component';
import { UrlManagerComponent } from '../url-manager/url-manager.component';
import { MemberManagerComponent } from '../member-manager/member-manager.component';
import { DeviceCardComponent } from '../../devices/device-card/device-card.component';
import { Household } from '../../../core/models/household.model';
import { Device } from '../../../core/models/session.model';

type DetailTab = 'devices' | 'floors' | 'rooms' | 'urls' | 'members' | 'settings';

@Component({
  selector: 'app-household-detail',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TimezoneSelectComponent,
    FloorManagerComponent,
    RoomManagerComponent,
    UrlManagerComponent,
    MemberManagerComponent,
    DeviceCardComponent,
  ],
  templateUrl: './household-detail.component.html',
  styleUrls: ['./household-detail.component.scss'],
})
export class HouseholdDetailComponent implements OnChanges {
  @Input() household!: Household;
  @Input() devices: Device[] = [];
  @Output() closed = new EventEmitter<void>();
  @Output() devicesChanged = new EventEmitter<void>();

  activeTab: DetailTab = 'devices';

  // Settings edit
  editingName = '';
  editingTz = '';
  savingSettings = false;
  settingsError = '';
  settingsSuccess = '';

  constructor(private householdService: HouseholdService, private auth: AuthService) {}

  ngOnChanges(): void {
    this.editingName = this.household?.name ?? '';
    this.editingTz = this.household?.timezone ?? '';
  }

  get isOwner(): boolean {
    const uid = this.auth.currentUser?.id;
    return this.household?.owner_id === uid;
  }

  get householdDevices(): Device[] {
    const roomIds = new Set((this.household?.rooms ?? []).map(r => r.id));
    return this.devices.filter(d => d.room_id !== null && roomIds.has(d.room_id!));
  }

  roomName(roomId: number | null): string {
    if (!roomId) return '—';
    return (this.household?.rooms ?? []).find(r => r.id === roomId)?.name ?? '—';
  }

  setTab(tab: DetailTab): void {
    this.activeTab = tab;
  }

  saveSettings(): void {
    this.savingSettings = true;
    this.settingsError = '';
    this.householdService
      .updateHousehold(this.household.id, this.editingName.trim(), this.editingTz || undefined)
      .subscribe({
        next: updated => {
          this.household = { ...this.household, name: updated.name, timezone: updated.timezone };
          this.savingSettings = false;
          this.settingsSuccess = 'Settings saved';
          setTimeout(() => (this.settingsSuccess = ''), 3000);
        },
        error: (e: Error) => {
          this.settingsError = e.message;
          this.savingSettings = false;
        },
      });
  }

  deleteHousehold(): void {
    if (!confirm(`Delete household "${this.household.name}"? All data will be removed.`)) return;
    this.householdService.deleteHousehold(this.household.id).subscribe({
      next: () => this.closed.emit(),
    });
  }

  onFloorsChanged(): void {
    this.reload();
  }

  onRoomsChanged(): void {
    this.reload();
  }

  onUrlsChanged(): void {
    this.reload();
  }

  onMembersChanged(): void {
    this.reload();
  }

  private reload(): void {
    this.householdService.getHousehold(this.household.id).subscribe({
      next: h => (this.household = h),
    });
  }

  close(): void {
    this.closed.emit();
  }
}
