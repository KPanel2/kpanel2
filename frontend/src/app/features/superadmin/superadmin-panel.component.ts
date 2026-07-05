import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { SuperadminService } from '../../core/services/superadmin.service';
import {
  AdminDevice,
  AdminHouseholdSummary,
  AdminOverview,
  AdminUrl,
  AdminUserSummary,
} from '../../core/models/admin.model';

type AdminSection = 'users' | 'households' | 'devices' | 'urls';

@Component({
  selector: 'app-superadmin-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './superadmin-panel.component.html',
  styleUrls: ['./superadmin-panel.component.scss'],
})
export class SuperadminPanelComponent implements OnInit {
  section: AdminSection = 'users';
  overview: AdminOverview | null = null;
  users: AdminUserSummary[] = [];
  households: AdminHouseholdSummary[] = [];
  devices: AdminDevice[] = [];
  urls: AdminUrl[] = [];
  loading = true;
  error = '';
  success = '';

  editingHouseholdId: number | null = null;
  editingDeviceCode: string | null = null;
  editingUrlId: number | null = null;

  householdName = '';
  householdTimezone = '';
  householdOwnerId = '';
  deviceOwnerId = '';
  deviceDisplayName = '';
  urlFriendlyName = '';
  urlTemplate = '';
  urlHouseholdId = '';
  memberEmail = '';

  constructor(private superadmin: SuperadminService) {}

  ngOnInit(): void {
    this.loadAll();
  }

  setSection(section: AdminSection): void {
    this.section = section;
    this.clearEdit();
  }

  loadAll(): void {
    this.loading = true;
    this.error = '';
    this.superadmin.getOverview().subscribe({
      next: overview => {
        this.overview = overview;
      },
      error: () => {},
    });
    this.superadmin.listUsers().subscribe({
      next: users => {
        this.users = users;
        this.loading = false;
      },
      error: (e: Error) => {
        this.error = e.message;
        this.loading = false;
      },
    });
    this.superadmin.listHouseholds().subscribe({
      next: households => {
        this.households = households;
      },
      error: () => {},
    });
    this.superadmin.listDevices().subscribe({
      next: devices => {
        this.devices = devices;
      },
      error: () => {},
    });
    this.superadmin.listUrls().subscribe({
      next: urls => {
        this.urls = urls;
      },
      error: () => {},
    });
  }

  toggleUserActive(user: AdminUserSummary): void {
    this.superadmin.updateUser(user.id, { is_active: !user.is_active }).subscribe({
      next: updated => {
        user.is_active = updated.is_active;
        this.flashSuccess(updated.is_active ? 'User activated' : 'User deactivated');
      },
      error: (e: Error) => (this.error = e.message),
    });
  }

  startEditHousehold(household: AdminHouseholdSummary): void {
    this.editingHouseholdId = household.id;
    this.householdName = household.name;
    this.householdTimezone = household.timezone ?? '';
    this.householdOwnerId = String(household.owner_id);
    this.memberEmail = '';
  }

  saveHousehold(householdId: number): void {
    const ownerId = Number(this.householdOwnerId);
    if (!Number.isFinite(ownerId) || ownerId <= 0) {
      this.error = 'Owner user ID must be a positive number';
      return;
    }
    this.superadmin.updateHousehold(householdId, {
      name: this.householdName.trim(),
      timezone: this.householdTimezone.trim() || null,
      owner_id: ownerId,
    }).subscribe({
      next: () => {
        this.flashSuccess('Household updated');
        this.clearEdit();
        this.reloadHouseholds();
      },
      error: (e: Error) => (this.error = e.message),
    });
  }

  addMember(householdId: number): void {
    if (!this.memberEmail.trim()) return;
    this.superadmin.addHouseholdMember(householdId, this.memberEmail.trim()).subscribe({
      next: () => {
        this.flashSuccess('Member added');
        this.memberEmail = '';
        this.reloadHouseholds();
      },
      error: (e: Error) => (this.error = e.message),
    });
  }

  startEditDevice(device: AdminDevice): void {
    this.editingDeviceCode = device.registration_code;
    this.deviceOwnerId = device.owner ? String(device.owner.id) : '';
    this.deviceDisplayName = device.display_name ?? '';
  }

  saveDevice(registrationCode: string): void {
    const body: { user_id?: number; unclaim?: boolean; display_name?: string } = {
      display_name: this.deviceDisplayName.trim(),
    };
    if (this.deviceOwnerId.trim()) {
      const ownerId = Number(this.deviceOwnerId);
      if (!Number.isFinite(ownerId) || ownerId <= 0) {
        this.error = 'Owner user ID must be a positive number';
        return;
      }
      body.user_id = ownerId;
    } else {
      body.unclaim = true;
    }
    this.superadmin.updateDevice(registrationCode, body).subscribe({
      next: () => {
        this.flashSuccess('Device updated');
        this.clearEdit();
        this.reloadDevices();
      },
      error: (e: Error) => (this.error = e.message),
    });
  }

  startEditUrl(url: AdminUrl): void {
    this.editingUrlId = url.id;
    this.urlFriendlyName = url.friendly_name;
    this.urlTemplate = url.url_template;
    this.urlHouseholdId = String(url.household_id);
  }

  saveUrl(urlId: number): void {
    const householdId = Number(this.urlHouseholdId);
    if (!Number.isFinite(householdId) || householdId <= 0) {
      this.error = 'Household ID must be a positive number';
      return;
    }
    this.superadmin.updateUrl(urlId, {
      friendly_name: this.urlFriendlyName.trim(),
      url_template: this.urlTemplate.trim(),
      household_id: householdId,
    }).subscribe({
      next: () => {
        this.flashSuccess('URL updated');
        this.clearEdit();
        this.reloadUrls();
      },
      error: (e: Error) => (this.error = e.message),
    });
  }

  private reloadHouseholds(): void {
    this.superadmin.listHouseholds().subscribe({
      next: households => (this.households = households),
    });
  }

  private reloadDevices(): void {
    this.superadmin.listDevices().subscribe({
      next: devices => (this.devices = devices),
    });
  }

  private reloadUrls(): void {
    this.superadmin.listUrls().subscribe({
      next: urls => (this.urls = urls),
    });
  }

  clearEdit(): void {
    this.editingHouseholdId = null;
    this.editingDeviceCode = null;
    this.editingUrlId = null;
  }

  private flashSuccess(message: string): void {
    this.success = message;
    this.error = '';
    setTimeout(() => (this.success = ''), 3000);
  }
}
