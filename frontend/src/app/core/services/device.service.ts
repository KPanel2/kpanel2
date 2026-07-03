import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { ApiService } from './api.service';
import { Device } from '../models/session.model';

interface DeviceUpdatePayload {
  display_name?: string;
  target_url?: string;
  timezone?: string;
  room_id?: number | null;
  clear_room?: boolean;
  url_mode?: string;
  household_url_id?: number | null;
}

@Injectable({ providedIn: 'root' })
export class DeviceService {
  constructor(private api: ApiService) {}

  listDevices(): Observable<Device[]> {
    return this.api.get<{ devices: Device[] }>('/api/v1/account/devices').pipe(map(r => r.devices));
  }

  claimDevice(registrationCode: string, householdId?: number, targetUrl?: string): Observable<Device> {
    const payload: Record<string, unknown> = { registration_code: registrationCode };
    if (householdId != null) payload['household_id'] = householdId;
    if (targetUrl) payload['target_url'] = targetUrl;
    return this.api.post<{ device: Device }>('/api/v1/account/devices/claim', payload).pipe(map(r => r.device));
  }

  updateDevice(code: string, payload: DeviceUpdatePayload): Observable<Device> {
    return this.api.patch<{ device: Device }>(`/api/v1/account/devices/${code}`, payload).pipe(map(r => r.device));
  }

  deleteDevice(code: string): Observable<unknown> {
    return this.api.delete(`/api/v1/account/devices/${code}`);
  }

  sendAction(code: string, action: 'reboot' | 'update'): Observable<unknown> {
    return this.api.post(`/api/v1/account/devices/${code}/actions/${action}`);
  }

  setTempUrl(code: string, tempUrl: string): Observable<Device> {
    return this.api.post<{ device: Device }>(`/api/v1/account/devices/${code}/temp-url`, {
      temp_url: tempUrl,
    }).pipe(map(r => r.device));
  }

  clearTempUrl(code: string): Observable<Device> {
    return this.api.delete<{ device: Device }>(`/api/v1/account/devices/${code}/temp-url`).pipe(map(r => r.device));
  }
}
