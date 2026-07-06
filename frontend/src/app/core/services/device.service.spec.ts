import { of } from 'rxjs';

import { DeviceService } from './device.service';
import { ApiService } from './api.service';
import { Device } from '../models/session.model';

describe('DeviceService', () => {
  let api: jasmine.SpyObj<ApiService>;
  let service: DeviceService;

  const device: Device = {
    registration_code: 'ABC123',
    device_id: 'dev-1',
    display_name: 'Kitchen',
    target_url: null,
    room_id: null,
    url_mode: null,
    household_url_id: null,
    has_temp_url: false,
    temp_url: null,
    temp_url_revert_mode: null,
    temp_url_revert_household_url_id: null,
    temp_url_set_at: null,
    resolved_url: null,
    timezone: null,
    client_version: null,
    latest_client_version: null,
    registered_at: '2026-01-01T00:00:00Z',
    last_seen: null,
  };

  beforeEach(() => {
    api = jasmine.createSpyObj<ApiService>('ApiService', ['get', 'post', 'patch', 'delete']);
    service = new DeviceService(api);
  });

  it('lists devices', (done) => {
    api.get.and.returnValue(of({ devices: [device] }));
    service.listDevices().subscribe(devices => {
      expect(devices).toEqual([device]);
      expect(api.get).toHaveBeenCalledWith('/api/v1/account/devices');
      done();
    });
  });

  it('claims a device with only the registration code', (done) => {
    api.post.and.returnValue(of({ device }));
    service.claimDevice('ABC123').subscribe(result => {
      expect(result).toEqual(device);
      expect(api.post).toHaveBeenCalledWith('/api/v1/account/devices/claim', {
        registration_code: 'ABC123',
      });
      done();
    });
  });

  it('claims a device with optional fields', (done) => {
    api.post.and.returnValue(of({ device }));
    service.claimDevice('ABC123', 5, 'https://example.com').subscribe(result => {
      expect(result).toEqual(device);
      expect(api.post).toHaveBeenCalledWith('/api/v1/account/devices/claim', {
        registration_code: 'ABC123',
        household_id: 5,
        target_url: 'https://example.com',
      });
      done();
    });
  });

  it('updates, deletes, and sends actions', () => {
    api.patch.and.returnValue(of({ device }));
    api.delete.and.returnValue(of({}));
    api.post.and.returnValue(of({}));

    service.updateDevice('ABC123', { display_name: 'Hall' }).subscribe();
    service.deleteDevice('ABC123').subscribe();
    service.sendAction('ABC123', 'reboot').subscribe();

    expect(api.patch).toHaveBeenCalledWith('/api/v1/account/devices/ABC123', { display_name: 'Hall' });
    expect(api.delete).toHaveBeenCalledWith('/api/v1/account/devices/ABC123');
    expect(api.post).toHaveBeenCalledWith('/api/v1/account/devices/ABC123/actions/reboot');
  });

  it('sets and clears temporary URLs', () => {
    api.post.and.returnValue(of({ device }));
    api.delete.and.returnValue(of({ device }));

    service.setTempUrl('ABC123', 'https://temp.example').subscribe();
    service.clearTempUrl('ABC123').subscribe();

    expect(api.post).toHaveBeenCalledWith('/api/v1/account/devices/ABC123/temp-url', {
      temp_url: 'https://temp.example',
    });
    expect(api.delete).toHaveBeenCalledWith('/api/v1/account/devices/ABC123/temp-url');
  });
});
