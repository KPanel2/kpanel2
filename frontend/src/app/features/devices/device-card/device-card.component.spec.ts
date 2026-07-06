import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DeviceCardComponent } from './device-card.component';
import { DeviceService } from '../../../core/services/device.service';
import { Device } from '../../../core/models/session.model';
import { of } from 'rxjs';

describe('DeviceCardComponent', () => {
  let fixture: ComponentFixture<DeviceCardComponent>;
  let component: DeviceCardComponent;

  const baseDevice: Device = {
    registration_code: 'KPANEL-TEST01',
    device_id: 'kpanel-test',
    display_name: 'Kitchen',
    target_url: 'https://panel.example.com',
    room_id: null,
    url_mode: 'custom',
    household_url_id: null,
    has_temp_url: false,
    temp_url: null,
    temp_url_revert_mode: null,
    temp_url_revert_household_url_id: null,
    temp_url_set_at: null,
    resolved_url: 'https://panel.example.com',
    timezone: 'America/Chicago',
    client_version: '1.0.0',
    latest_client_version: '2.0.0',
    registered_at: '2026-01-01T00:00:00Z',
    last_seen: '2026-01-02T00:00:00Z',
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DeviceCardComponent],
      providers: [
        {
          provide: DeviceService,
          useValue: {
            updateDevice: () => of(baseDevice),
            deleteDevice: () => of({}),
            sendAction: () => of({}),
            setTempUrl: () => of(baseDevice),
            clearTempUrl: () => of(baseDevice),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(DeviceCardComponent);
    component = fixture.componentInstance;
    component.device = { ...baseDevice };
    component.households = [];
    fixture.detectChanges();
  });

  it('flags devices that need an update', () => {
    expect(component.needsUpdate).toBeTrue();
  });

  it('shows current and latest available versions', () => {
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Current version');
    expect(text).toContain('1.0.0');
    expect(text).toContain('Latest available');
    expect(text).toContain('2.0.0');
    expect(text).toContain('Update needed');
  });

  it('shows version details even when the current version is missing', () => {
    component.device = { ...baseDevice, client_version: null };
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Current version');
    expect(text).toContain('Not reported');
    expect(text).toContain('Latest available');
    expect(text).toContain('2.0.0');
    expect(component.needsUpdate).toBeFalse();
  });

  it('shows up to date when current matches latest', () => {
    component.device = { ...baseDevice, client_version: '2.0.0', latest_client_version: '2.0.0' };
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Up to date');
    expect(component.needsUpdate).toBeFalse();
  });

  it('shows last seen when provided by the API alias', () => {
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Last seen');
  });
});
