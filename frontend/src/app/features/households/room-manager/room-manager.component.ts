import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HouseholdService } from '../../../core/services/household.service';
import { Household, Floor, Room } from '../../../core/models/household.model';

@Component({
  selector: 'app-room-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './room-manager.component.html',
})
export class RoomManagerComponent {
  @Input() household!: Household;
  @Output() roomsChanged = new EventEmitter<void>();

  creating = false;
  newName = '';
  newFloorId: number | null = null;
  newOrder = 0;
  editingRoom: Room | null = null;
  editName = '';
  editFloorId: number | null = null;
  editOrder = 0;
  error = '';

  constructor(private householdService: HouseholdService) {}

  get floors(): Floor[] {
    return this.household?.floors ?? [];
  }

  get rooms(): Room[] {
    return (this.household?.rooms ?? []).slice().sort((a, b) => a.sort_order - b.sort_order);
  }

  floorName(floorId: number | null): string {
    if (!floorId) return '—';
    return this.floors.find(f => f.id === floorId)?.name ?? '?';
  }

  create(): void {
    if (!this.newName.trim()) return;
    this.householdService
      .createRoom(this.household.id, this.newName.trim(), this.newFloorId ?? undefined, this.newOrder)
      .subscribe({
        next: () => {
          this.newName = '';
          this.newFloorId = null;
          this.newOrder = 0;
          this.creating = false;
          this.roomsChanged.emit();
        },
        error: (e: Error) => (this.error = e.message),
      });
  }

  startEdit(room: Room): void {
    this.editingRoom = room;
    this.editName = room.name;
    this.editFloorId = room.floor_id;
    this.editOrder = room.sort_order;
    this.error = '';
  }

  saveEdit(): void {
    if (!this.editingRoom) return;
    this.householdService
      .updateRoom(this.household.id, this.editingRoom.id, this.editName.trim(), this.editFloorId, this.editOrder)
      .subscribe({
        next: () => {
          this.editingRoom = null;
          this.roomsChanged.emit();
        },
        error: (e: Error) => (this.error = e.message),
      });
  }

  delete(room: Room): void {
    if (!confirm(`Delete room "${room.name}"? Devices in this room will be unassigned.`)) return;
    this.householdService.deleteRoom(this.household.id, room.id).subscribe({
      next: () => this.roomsChanged.emit(),
      error: (e: Error) => (this.error = e.message),
    });
  }
}
