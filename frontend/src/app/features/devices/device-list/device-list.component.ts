import { Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DeviceCardComponent } from '../device-card/device-card.component';
import { Device } from '../../../core/models/session.model';
import { Household } from '../../../core/models/household.model';

@Component({
  selector: 'app-device-list',
  standalone: true,
  imports: [CommonModule, DeviceCardComponent],
  templateUrl: './device-list.component.html',
})
export class DeviceListComponent {
  @Input() devices: Device[] = [];
  @Input() households: Household[] = [];
  @Input() loading = false;
  @Output() devicesChanged = new EventEmitter<void>();
}
