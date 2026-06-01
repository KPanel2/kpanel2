import { Component, forwardRef, Input } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR, FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { TIMEZONES } from '../../constants/timezones';

@Component({
  selector: 'app-timezone-select',
  standalone: true,
  imports: [CommonModule, FormsModule],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => TimezoneSelectComponent),
      multi: true,
    },
  ],
  template: `
    <select [ngModel]="value" (ngModelChange)="onChange($event)" (blur)="onTouched()">
      <option *ngIf="placeholder" value="">{{ placeholder }}</option>
      <option *ngFor="let tz of timezones" [value]="tz">{{ tz }}</option>
    </select>
  `,
})
export class TimezoneSelectComponent implements ControlValueAccessor {
  @Input() placeholder = '';
  timezones = TIMEZONES;
  value = '';

  onChange: (v: string) => void = () => {};
  onTouched: () => void = () => {};

  writeValue(v: string): void {
    this.value = v ?? '';
  }

  registerOnChange(fn: (v: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }
}
