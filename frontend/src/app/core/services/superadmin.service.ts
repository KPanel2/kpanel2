import { Injectable } from '@angular/core';
import { Observable, map } from 'rxjs';

import { ApiService } from './api.service';
import {
  AdminDevice,
  AdminHouseholdSummary,
  AdminOverview,
  AdminUrl,
  AdminUserDetail,
  AdminUserSummary,
} from '../models/admin.model';
import { Household } from '../models/household.model';

@Injectable({ providedIn: 'root' })
export class SuperadminService {
  constructor(private api: ApiService) {}

  getOverview(): Observable<AdminOverview> {
    return this.api.get<AdminOverview>('/api/v1/superadmin/overview');
  }

  listUsers(): Observable<AdminUserSummary[]> {
    return this.api.get<{ users: AdminUserSummary[] }>('/api/v1/superadmin/users').pipe(map(r => r.users));
  }

  getUser(userId: number): Observable<AdminUserDetail> {
    return this.api.get<AdminUserDetail>(`/api/v1/superadmin/users/${userId}`);
  }

  updateUser(userId: number, body: { is_active?: boolean }): Observable<AdminUserSummary> {
    return this.api.patch<{ user: AdminUserSummary }>(`/api/v1/superadmin/users/${userId}`, body).pipe(map(r => r.user));
  }

  listHouseholds(): Observable<AdminHouseholdSummary[]> {
    return this.api.get<{ households: AdminHouseholdSummary[] }>('/api/v1/superadmin/households').pipe(map(r => r.households));
  }

  getHousehold(householdId: number): Observable<Household> {
    return this.api.get<{ household: Household }>(`/api/v1/superadmin/households/${householdId}`).pipe(map(r => r.household));
  }

  updateHousehold(
    householdId: number,
    body: { name?: string; timezone?: string | null; owner_id?: number },
  ): Observable<Household> {
    return this.api.patch<{ household: Household }>(`/api/v1/superadmin/households/${householdId}`, body).pipe(map(r => r.household));
  }

  addHouseholdMember(householdId: number, email: string, role: 'owner' | 'member' = 'member'): Observable<Household> {
    return this.api.post<{ household: Household }>(`/api/v1/superadmin/households/${householdId}/members`, { email, role }).pipe(map(r => r.household));
  }

  removeHouseholdMember(householdId: number, userId: number): Observable<Household> {
    return this.api.delete<{ household: Household }>(`/api/v1/superadmin/households/${householdId}/members/${userId}`).pipe(map(r => r.household));
  }

  listDevices(): Observable<AdminDevice[]> {
    return this.api.get<{ devices: AdminDevice[] }>('/api/v1/superadmin/devices').pipe(map(r => r.devices));
  }

  updateDevice(
    registrationCode: string,
    body: {
      user_id?: number;
      unclaim?: boolean;
      display_name?: string;
      target_url?: string;
      timezone?: string | null;
    },
  ): Observable<AdminDevice> {
    return this.api.patch<{ device: AdminDevice }>(`/api/v1/superadmin/devices/${registrationCode}`, body).pipe(map(r => r.device));
  }

  listUrls(): Observable<AdminUrl[]> {
    return this.api.get<{ urls: AdminUrl[] }>('/api/v1/superadmin/urls').pipe(map(r => r.urls));
  }

  updateUrl(
    urlId: number,
    body: {
      friendly_name?: string;
      url_template?: string;
      is_default?: boolean;
      household_id?: number;
    },
  ): Observable<AdminUrl> {
    return this.api.patch<{ url: AdminUrl }>(`/api/v1/superadmin/urls/${urlId}`, body).pipe(map(r => r.url));
  }
}
