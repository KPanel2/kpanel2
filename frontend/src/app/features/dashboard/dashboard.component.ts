import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { DeviceService } from '../../core/services/device.service';
import { HouseholdService } from '../../core/services/household.service';
import { ProfileCardComponent } from './profile-card/profile-card.component';
import { DeviceListComponent } from '../devices/device-list/device-list.component';
import { ClaimDeviceComponent } from '../devices/claim-device/claim-device.component';
import { HouseholdListComponent } from '../households/household-list/household-list.component';
import { User, Device } from '../../core/models/session.model';
import { Household } from '../../core/models/household.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ProfileCardComponent,
    DeviceListComponent,
    ClaimDeviceComponent,
    HouseholdListComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit {
  user: User | undefined;
  devices: Device[] = [];
  households: Household[] = [];
  activeTab: 'devices' | 'households' = 'devices';
  loadingDevices = true;
  loadingHouseholds = true;

  constructor(
    private auth: AuthService,
    private router: Router,
    private deviceService: DeviceService,
    private householdService: HouseholdService
  ) {}

  ngOnInit(): void {
    this.auth.session$.subscribe(s => {
      this.user = s?.user;
    });
    this.loadDevices();
    this.loadHouseholds();
  }

  loadDevices(): void {
    this.loadingDevices = true;
    this.deviceService.listDevices().subscribe({
      next: devices => {
        this.devices = devices;
        this.loadingDevices = false;
      },
      error: () => (this.loadingDevices = false),
    });
  }

  loadHouseholds(): void {
    this.loadingHouseholds = true;
    this.householdService.listHouseholds().subscribe({
      next: h => {
        this.households = h;
        this.loadingHouseholds = false;
      },
      error: () => (this.loadingHouseholds = false),
    });
  }

  onDeviceClaimed(): void {
    this.loadDevices();
  }

  onDevicesChanged(): void {
    this.loadDevices();
  }

  onHouseholdsChanged(): void {
    this.loadHouseholds();
    this.loadDevices();
  }

  setTab(tab: 'devices' | 'households'): void {
    this.activeTab = tab;
  }

  logout(): void {
    this.auth.logout().subscribe({
      next: () => {
        this.auth.loadSession().subscribe({
          next: () => this.router.navigate(['/login']),
          error: () => this.router.navigate(['/login']),
        });
      },
      error: () => this.router.navigate(['/login']),
    });
  }
}
