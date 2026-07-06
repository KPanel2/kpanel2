import { of } from 'rxjs';

import { SuperadminService } from './superadmin.service';
import { ApiService } from './api.service';

describe('SuperadminService', () => {
  let api: jasmine.SpyObj<ApiService>;
  let service: SuperadminService;

  beforeEach(() => {
    api = jasmine.createSpyObj<ApiService>('ApiService', ['get', 'post', 'patch', 'delete']);
    service = new SuperadminService(api);
  });

  it('loads overview and users', () => {
    api.get.and.returnValue(of({ users: [] }));
    service.getOverview().subscribe();
    service.listUsers().subscribe();
    service.getUser(1).subscribe();

    expect(api.get).toHaveBeenCalledWith('/api/v1/superadmin/overview');
    expect(api.get).toHaveBeenCalledWith('/api/v1/superadmin/users');
    expect(api.get).toHaveBeenCalledWith('/api/v1/superadmin/users/1');
  });

  it('updates users and households', () => {
    api.patch.and.returnValue(of({ user: { id: 1 } }));
    api.get.and.returnValue(of({ household: { id: 2 } }));

    service.updateUser(1, { is_active: false }).subscribe();
    service.getHousehold(2).subscribe();
    service.updateHousehold(2, { name: 'Renamed' }).subscribe();

    expect(api.patch).toHaveBeenCalledWith('/api/v1/superadmin/users/1', { is_active: false });
    expect(api.patch).toHaveBeenCalledWith('/api/v1/superadmin/households/2', { name: 'Renamed' });
  });

  it('manages household membership', () => {
    api.get.and.returnValue(of({ households: [] }));
    api.post.and.returnValue(of({ household: { id: 1 } }));
    api.delete.and.returnValue(of({ household: { id: 1 } }));

    service.listHouseholds().subscribe();
    service.addHouseholdMember(1, 'owner@example.com', 'owner').subscribe();
    service.addHouseholdMember(2, 'member@example.com').subscribe();
    service.removeHouseholdMember(1, 9).subscribe();

    expect(api.post).toHaveBeenCalledWith('/api/v1/superadmin/households/1/members', {
      email: 'owner@example.com',
      role: 'owner',
    });
    expect(api.post).toHaveBeenCalledWith('/api/v1/superadmin/households/2/members', {
      email: 'member@example.com',
      role: 'member',
    });
    expect(api.delete).toHaveBeenCalledWith('/api/v1/superadmin/households/1/members/9');
  });

  it('manages devices and URLs', () => {
    api.get.and.returnValue(of({ devices: [] }));
    api.patch.and.returnValue(of({ device: { registration_code: 'ABC' } }));
    api.get.and.returnValue(of({ urls: [] }));

    service.listDevices().subscribe();
    service.updateDevice('ABC', { unclaim: true }).subscribe();
    service.listUrls().subscribe();
    service.updateUrl(3, { friendly_name: 'Main' }).subscribe();

    expect(api.patch).toHaveBeenCalledWith('/api/v1/superadmin/devices/ABC', { unclaim: true });
    expect(api.patch).toHaveBeenCalledWith('/api/v1/superadmin/urls/3', { friendly_name: 'Main' });
  });
});
