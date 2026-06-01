import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { ApiService } from './api.service';
import { Household, Floor, Room, HouseholdUrl, Member } from '../models/household.model';

@Injectable({ providedIn: 'root' })
export class HouseholdService {
  constructor(private api: ApiService) {}

  // ─── Households ───────────────────────────────────────────────────────────

  listHouseholds(): Observable<Household[]> {
    return this.api.get<{ households: Household[] }>('/api/v1/households').pipe(map(r => r.households));
  }

  getHousehold(id: number): Observable<Household> {
    return this.api.get<{ household: Household }>(`/api/v1/households/${id}`).pipe(map(r => r.household));
  }

  createHousehold(name: string, timezone?: string): Observable<Household> {
    return this.api.post<{ household: Household }>('/api/v1/households', { name, timezone }).pipe(map(r => r.household));
  }

  updateHousehold(id: number, name: string, timezone?: string): Observable<Household> {
    return this.api.patch<{ household: Household }>(`/api/v1/households/${id}`, { name, timezone }).pipe(map(r => r.household));
  }

  deleteHousehold(id: number): Observable<unknown> {
    return this.api.delete(`/api/v1/households/${id}`);
  }

  // ─── Members ──────────────────────────────────────────────────────────────

  listMembers(householdId: number): Observable<Member[]> {
    return this.api.get<{ members: Member[] }>(`/api/v1/households/${householdId}/members`).pipe(map(r => r.members));
  }

  addMember(householdId: number, email: string): Observable<Member> {
    return this.api.post<{ member: Member }>(`/api/v1/households/${householdId}/members`, { email }).pipe(map(r => r.member));
  }

  removeMember(householdId: number, userId: number): Observable<unknown> {
    return this.api.delete(`/api/v1/households/${householdId}/members/${userId}`);
  }

  // ─── Floors ───────────────────────────────────────────────────────────────

  listFloors(householdId: number): Observable<Floor[]> {
    return this.api.get<{ floors: Floor[] }>(`/api/v1/households/${householdId}/floors`).pipe(map(r => r.floors));
  }

  createFloor(householdId: number, name: string, sortOrder = 0): Observable<Floor> {
    return this.api.post<{ floor: Floor }>(`/api/v1/households/${householdId}/floors`, {
      name,
      sort_order: sortOrder,
    }).pipe(map(r => r.floor));
  }

  updateFloor(householdId: number, floorId: number, name: string, sortOrder?: number): Observable<Floor> {
    return this.api.patch<{ floor: Floor }>(`/api/v1/households/${householdId}/floors/${floorId}`, {
      name,
      sort_order: sortOrder,
    }).pipe(map(r => r.floor));
  }

  deleteFloor(householdId: number, floorId: number): Observable<unknown> {
    return this.api.delete(`/api/v1/households/${householdId}/floors/${floorId}`);
  }

  // ─── Rooms ────────────────────────────────────────────────────────────────

  listRooms(householdId: number): Observable<Room[]> {
    return this.api.get<{ rooms: Room[] }>(`/api/v1/households/${householdId}/rooms`).pipe(map(r => r.rooms));
  }

  createRoom(householdId: number, name: string, floorId?: number, sortOrder = 0): Observable<Room> {
    return this.api.post<{ room: Room }>(`/api/v1/households/${householdId}/rooms`, {
      name,
      floor_id: floorId ?? null,
      sort_order: sortOrder,
    }).pipe(map(r => r.room));
  }

  updateRoom(
    householdId: number,
    roomId: number,
    name: string,
    floorId?: number | null,
    sortOrder?: number
  ): Observable<Room> {
    return this.api.patch<{ room: Room }>(`/api/v1/households/${householdId}/rooms/${roomId}`, {
      name,
      floor_id: floorId ?? null,
      sort_order: sortOrder,
    }).pipe(map(r => r.room));
  }

  deleteRoom(householdId: number, roomId: number): Observable<unknown> {
    return this.api.delete(`/api/v1/households/${householdId}/rooms/${roomId}`);
  }

  // ─── URLs ─────────────────────────────────────────────────────────────────

  listUrls(householdId: number): Observable<HouseholdUrl[]> {
    return this.api.get<{ urls: HouseholdUrl[] }>(`/api/v1/households/${householdId}/urls`).pipe(map(r => r.urls));
  }

  createUrl(householdId: number, friendlyName: string, urlTemplate: string, isDefault = false): Observable<HouseholdUrl> {
    return this.api.post<{ url: HouseholdUrl }>(`/api/v1/households/${householdId}/urls`, {
      friendly_name: friendlyName,
      url_template: urlTemplate,
      is_default: isDefault,
    }).pipe(map(r => r.url));
  }

  updateUrl(
    householdId: number,
    urlId: number,
    friendlyName: string,
    urlTemplate: string,
    isDefault?: boolean
  ): Observable<HouseholdUrl> {
    return this.api.patch<{ url: HouseholdUrl }>(`/api/v1/households/${householdId}/urls/${urlId}`, {
      friendly_name: friendlyName,
      url_template: urlTemplate,
      is_default: isDefault,
    }).pipe(map(r => r.url));
  }

  deleteUrl(householdId: number, urlId: number): Observable<unknown> {
    return this.api.delete(`/api/v1/households/${householdId}/urls/${urlId}`);
  }

  setDefaultUrl(householdId: number, urlId: number): Observable<HouseholdUrl> {
    return this.api.post<{ url: HouseholdUrl }>(
      `/api/v1/households/${householdId}/urls/${urlId}/set-default`
    ).pipe(map(r => r.url));
  }
}
