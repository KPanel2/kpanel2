import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DeviceCardComponent } from './device-card.component';
import { DeviceService } from '../../../core/services/device.service';
import { Device } from '../../../core/models/session.model';
import { of } from 'rxjs';

describe('DeviceCardComponent', () => {
  let fixture: ComponentFixture<DeviceCardComponent>;
  let component: DeviceCardComponent;
  let deviceService: jasmine.SpyObj<DeviceService>;

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
    ha_bootstrap_url: null,
    has_ha_binding: false,
    has_local_ha_binding: false,
    ha_binding_source: null,
    effective_ha_bootstrap_url: null,
  };

  beforeEach(async () => {
    deviceService = jasmine.createSpyObj<DeviceService>('DeviceService', [
      'updateDevice',
      'deleteDevice',
      'sendAction',
      'setTempUrl',
      'clearTempUrl',
    ]);
    deviceService.updateDevice.and.returnValue(of(baseDevice));
    deviceService.deleteDevice.and.returnValue(of({}));
    deviceService.sendAction.and.returnValue(of({}));
    deviceService.setTempUrl.and.returnValue(of(baseDevice));
    deviceService.clearTempUrl.and.returnValue(of(baseDevice));

    await TestBed.configureTestingModule({
      imports: [DeviceCardComponent],
      providers: [{ provide: DeviceService, useValue: deviceService }],
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

  it('shows HA binding status when configured', () => {
    component.device = {
      ...baseDevice,
      has_ha_binding: true,
      has_local_ha_binding: true,
      ha_binding_source: 'device',
      ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
      effective_ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
    };
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('HA binding');
    expect(text).toContain('Configured');
  });

  it('shows inherited HA binding source', () => {
    component.device = {
      ...baseDevice,
      has_ha_binding: true,
      has_local_ha_binding: false,
      ha_binding_source: 'household',
      ha_bootstrap_url: null,
      effective_ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
    };
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Inherited from household');
    expect(text).toContain('https://ha.example/api/kpanel_dashboard/bootstrap');
  });

  it('loads HA bootstrap URL and resets secret fields on changes', () => {
    component.device = {
      ...baseDevice,
      has_ha_binding: true,
      has_local_ha_binding: true,
      ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
    };
    component.haBindingSecret = 'stale-secret';
    component.clearHaBinding = true;

    component.ngOnChanges();

    expect(component.haBootstrapUrl).toBe(
      'https://ha.example/api/kpanel_dashboard/bootstrap'
    );
    expect(component.haBindingSecret).toBe('');
    expect(component.clearHaBinding).toBeFalse();
  });

  it('includes HA binding fields when saving edits', () => {
    component.startEdit();
    component.haBootstrapUrl = 'https://ha.example/api/kpanel_dashboard/bootstrap';
    component.haBindingSecret = 'binding-secret';
    component.saveEdit();

    expect(deviceService.updateDevice).toHaveBeenCalledWith(
      'KPANEL-TEST01',
      jasmine.objectContaining({
        ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
        ha_binding_secret: 'binding-secret',
      })
    );
  });

  it('clears HA binding when requested', () => {
    component.device = {
      ...baseDevice,
      has_ha_binding: true,
      has_local_ha_binding: true,
      ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
    };
    component.startEdit();
    component.clearHaBinding = true;
    component.saveEdit();

    expect(deviceService.updateDevice).toHaveBeenCalledWith(
      'KPANEL-TEST01',
      jasmine.objectContaining({ clear_ha_binding: true })
    );
  });
});
