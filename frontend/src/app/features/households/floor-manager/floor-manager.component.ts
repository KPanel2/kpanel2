import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HouseholdService } from '../../../core/services/household.service';
import { Household, Floor } from '../../../core/models/household.model';

@Component({
  selector: 'app-floor-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './floor-manager.component.html',
})
export class FloorManagerComponent {
  @Input() household!: Household;
  @Output() floorsChanged = new EventEmitter<void>();

  creating = false;
  newName = '';
  newOrder = 0;
  editingFloor: Floor | null = null;
  editName = '';
  editOrder = 0;
  error = '';

  constructor(private householdService: HouseholdService) {}

  get floors(): Floor[] {
    return (this.household?.floors ?? []).slice().sort((a, b) => a.sort_order - b.sort_order);
  }

  create(): void {
    if (!this.newName.trim()) return;
    this.householdService
      .createFloor(this.household.id, this.newName.trim(), this.newOrder)
      .subscribe({
        next: () => {
          this.newName = '';
          this.newOrder = 0;
          this.creating = false;
          this.floorsChanged.emit();
        },
        error: (e: Error) => (this.error = e.message),
      });
  }

  startEdit(floor: Floor): void {
    this.editingFloor = floor;
    this.editName = floor.name;
    this.editOrder = floor.sort_order;
    this.error = '';
  }

  saveEdit(): void {
    if (!this.editingFloor) return;
    this.householdService
      .updateFloor(this.household.id, this.editingFloor.id, this.editName.trim(), this.editOrder)
      .subscribe({
        next: () => {
          this.editingFloor = null;
          this.floorsChanged.emit();
        },
        error: (e: Error) => (this.error = e.message),
      });
  }

  delete(floor: Floor): void {
    if (!confirm(`Delete floor "${floor.name}"? Rooms on this floor will become unassigned.`)) return;
    this.householdService.deleteFloor(this.household.id, floor.id).subscribe({
      next: () => this.floorsChanged.emit(),
      error: (e: Error) => (this.error = e.message),
    });
  }
}
