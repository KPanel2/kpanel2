import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { HouseholdService } from '../../../core/services/household.service';
import { AuthService } from '../../../core/services/auth.service';
import { TimezoneSelectComponent } from '../../../shared/components/timezone-select/timezone-select.component';
import { HouseholdDetailComponent } from '../household-detail/household-detail.component';
import { Household } from '../../../core/models/household.model';
import { Device } from '../../../core/models/session.model';

@Component({
  selector: 'app-household-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, TimezoneSelectComponent, HouseholdDetailComponent],
  templateUrl: './household-list.component.html',
  styleUrls: ['./household-list.component.scss'],
})
export class HouseholdListComponent {
  @Input() households: Household[] = [];
  @Input() devices: Device[] = [];
  @Input() loading = false;
  @Output() householdsChanged = new EventEmitter<void>();

  creating = false;
  newName = '';
  newTimezone = '';
  saving = false;
  error = '';

  selectedHousehold: Household | null = null;

  constructor(private householdService: HouseholdService, private auth: AuthService) {}

  get userTimezone(): string {
    return this.auth.currentUser?.timezone ?? 'UTC';
  }

  startCreate(): void {
    this.creating = true;
    this.newName = '';
    this.newTimezone = this.userTimezone;
    this.error = '';
  }

  cancelCreate(): void {
    this.creating = false;
  }

  create(): void {
    if (!this.newName.trim()) return;
    this.saving = true;
    this.householdService.createHousehold(this.newName.trim(), this.newTimezone || undefined).subscribe({
      next: () => {
        this.saving = false;
        this.creating = false;
        this.householdsChanged.emit();
      },
      error: (e: Error) => {
        this.error = e.message;
        this.saving = false;
      },
    });
  }

  openHousehold(h: Household): void {
    // Load full household detail
    this.householdService.getHousehold(h.id).subscribe({
      next: full => (this.selectedHousehold = full),
    });
  }

  closeDetail(): void {
    this.selectedHousehold = null;
    this.householdsChanged.emit();
  }
}
