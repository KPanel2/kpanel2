import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HouseholdService } from '../../../core/services/household.service';
import { Household, HouseholdUrl } from '../../../core/models/household.model';

@Component({
  selector: 'app-url-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './url-manager.component.html',
})
export class UrlManagerComponent {
  @Input() household!: Household;
  @Output() urlsChanged = new EventEmitter<void>();

  creating = false;
  newFriendlyName = '';
  newTemplate = '';
  newIsDefault = false;
  editingUrl: HouseholdUrl | null = null;
  editFriendlyName = '';
  editTemplate = '';
  error = '';

  constructor(private householdService: HouseholdService) {}

  get urls(): HouseholdUrl[] {
    return this.household?.urls ?? [];
  }

  create(): void {
    if (!this.newFriendlyName.trim() || !this.newTemplate.trim()) return;
    this.householdService
      .createUrl(this.household.id, this.newFriendlyName.trim(), this.newTemplate.trim(), this.newIsDefault)
      .subscribe({
        next: () => {
          this.newFriendlyName = '';
          this.newTemplate = '';
          this.newIsDefault = false;
          this.creating = false;
          this.urlsChanged.emit();
        },
        error: (e: Error) => (this.error = e.message),
      });
  }

  startEdit(url: HouseholdUrl): void {
    this.editingUrl = url;
    this.editFriendlyName = url.friendly_name;
    this.editTemplate = url.url_template;
    this.error = '';
  }

  saveEdit(): void {
    if (!this.editingUrl) return;
    this.householdService
      .updateUrl(this.household.id, this.editingUrl.id, this.editFriendlyName.trim(), this.editTemplate.trim())
      .subscribe({
        next: () => {
          this.editingUrl = null;
          this.urlsChanged.emit();
        },
        error: (e: Error) => (this.error = e.message),
      });
  }

  setDefault(url: HouseholdUrl): void {
    this.householdService.setDefaultUrl(this.household.id, url.id).subscribe({
      next: () => this.urlsChanged.emit(),
      error: (e: Error) => (this.error = e.message),
    });
  }

  delete(url: HouseholdUrl): void {
    if (!confirm(`Delete URL "${url.friendly_name}"?`)) return;
    this.householdService.deleteUrl(this.household.id, url.id).subscribe({
      next: () => this.urlsChanged.emit(),
      error: (e: Error) => (this.error = e.message),
    });
  }
}
