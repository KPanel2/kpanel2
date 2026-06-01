import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HouseholdService } from '../../../core/services/household.service';
import { AuthService } from '../../../core/services/auth.service';
import { Household, Member } from '../../../core/models/household.model';

@Component({
  selector: 'app-member-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './member-manager.component.html',
})
export class MemberManagerComponent {
  @Input() household!: Household;
  @Input() isOwner = false;
  @Output() membersChanged = new EventEmitter<void>();

  adding = false;
  newEmail = '';
  error = '';
  success = '';

  constructor(private householdService: HouseholdService, private auth: AuthService) {}

  get members(): Member[] {
    return this.household?.members ?? [];
  }

  get currentUserId(): number | undefined {
    return this.auth.currentUser?.id;
  }

  addMember(): void {
    if (!this.newEmail.trim()) return;
    this.householdService.addMember(this.household.id, this.newEmail.trim()).subscribe({
      next: () => {
        this.newEmail = '';
        this.adding = false;
        this.success = 'Member added';
        this.membersChanged.emit();
        setTimeout(() => (this.success = ''), 3000);
      },
      error: (e: Error) => (this.error = e.message),
    });
  }

  removeMember(member: Member): void {
    if (!confirm(`Remove ${member.display_name || member.email} from this household?`)) return;
    this.householdService.removeMember(this.household.id, member.user_id).subscribe({
      next: () => this.membersChanged.emit(),
      error: (e: Error) => (this.error = e.message),
    });
  }
}
