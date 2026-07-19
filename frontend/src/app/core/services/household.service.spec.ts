import { of } from 'rxjs';

import { HouseholdService } from './household.service';
import { ApiService } from './api.service';

describe('HouseholdService', () => {
  let api: jasmine.SpyObj<ApiService>;
  let service: HouseholdService;

  beforeEach(() => {
    api = jasmine.createSpyObj<ApiService>('ApiService', ['get', 'post', 'patch', 'delete']);
    service = new HouseholdService(api);
  });

  it('lists and fetches households', () => {
    api.get.and.returnValue(of({ households: [{ id: 1, name: 'Home' }] }));
    service.listHouseholds().subscribe();
    service.getHousehold(1).subscribe();
    expect(api.get).toHaveBeenCalledWith('/api/v1/households');
    expect(api.get).toHaveBeenCalledWith('/api/v1/households/1');
  });

  it('creates, updates, and deletes households', () => {
    api.post.and.returnValue(of({ household: { id: 1 } }));
    api.patch.and.returnValue(of({ household: { id: 1 } }));
    api.delete.and.returnValue(of({}));

    service.createHousehold('Home', 'UTC').subscribe();
    service.updateHousehold(1, 'Renamed', 'UTC').subscribe();
    service.deleteHousehold(1).subscribe();

    expect(api.post).toHaveBeenCalledWith('/api/v1/households', { name: 'Home', timezone: 'UTC' });
    expect(api.patch).toHaveBeenCalledWith('/api/v1/households/1', { name: 'Renamed', timezone: 'UTC' });
    expect(api.delete).toHaveBeenCalledWith('/api/v1/households/1');
  });

  it('manages members', () => {
    api.get.and.returnValue(of({ members: [] }));
    api.post.and.returnValue(of({ member: { id: 1 } }));
    api.delete.and.returnValue(of({}));

    service.listMembers(1).subscribe();
    service.addMember(1, 'user@example.com').subscribe();
    service.removeMember(1, 9).subscribe();

    expect(api.get).toHaveBeenCalledWith('/api/v1/households/1/members');
    expect(api.post).toHaveBeenCalledWith('/api/v1/households/1/members', { email: 'user@example.com' });
    expect(api.delete).toHaveBeenCalledWith('/api/v1/households/1/members/9');
  });

  it('manages floors and rooms', () => {
    api.get.and.returnValue(of({ floors: [] }));
    api.post.and.returnValue(of({ floor: { id: 1 } }));
    api.patch.and.returnValue(of({ floor: { id: 1 } }));
    api.delete.and.returnValue(of({}));

    service.listFloors(1).subscribe();
    service.createFloor(1, 'Ground', 0).subscribe();
    service.updateFloor(1, 2, 'First', 1).subscribe();
    service.deleteFloor(1, 2).subscribe();

    service.listRooms(1).subscribe();
    api.post.and.returnValue(of({ room: { id: 3 } }));
    service.createRoom(1, 'Kitchen', 2, 0, 'kitchen').subscribe();
    api.patch.and.returnValue(of({ room: { id: 3 } }));
    service.updateRoom(1, 3, 'Dining', null, 1, 'dining').subscribe();
    service.deleteRoom(1, 3).subscribe();

    expect(api.post).toHaveBeenCalledWith('/api/v1/households/1/rooms', {
      name: 'Kitchen',
      floor_id: 2,
      sort_order: 0,
      slug: 'kitchen',
    });
    expect(api.patch).toHaveBeenCalledWith('/api/v1/households/1/rooms/3', {
      name: 'Dining',
      floor_id: null,
      sort_order: 1,
      slug: 'dining',
      clear_slug: false,
    });
  });

  it('manages household URLs', () => {
    api.get.and.returnValue(of({ urls: [] }));
    api.post.and.returnValue(of({ url: { id: 1 } }));
    api.patch.and.returnValue(of({ url: { id: 1 } }));
    api.delete.and.returnValue(of({}));

    service.listUrls(1).subscribe();
    service.createUrl(1, 'Default', 'https://{room}.example', true).subscribe();
    service.updateUrl(1, 2, 'Alt', 'https://alt.example', false).subscribe();
    service.deleteUrl(1, 2).subscribe();
    service.setDefaultUrl(1, 2).subscribe();

    expect(api.post).toHaveBeenCalledWith('/api/v1/households/1/urls', {
      friendly_name: 'Default',
      url_template: 'https://{room}.example',
      is_default: true,
    });
    expect(api.post).toHaveBeenCalledWith('/api/v1/households/1/urls/2/set-default');
  });

  it('creates rooms without an explicit floor', () => {
    api.post.and.returnValue(of({ room: { id: 3 } }));
    service.createRoom(1, 'Kitchen').subscribe();
    expect(api.post).toHaveBeenCalledWith('/api/v1/households/1/rooms', {
      name: 'Kitchen',
      floor_id: null,
      sort_order: 0,
      slug: null,
    });
  });

  it('clears a room slug on update', () => {
    api.patch.and.returnValue(of({ room: { id: 3, slug: null } }));
    service.updateRoom(1, 3, 'Dining', null, 1, null, true).subscribe();
    expect(api.patch).toHaveBeenCalledWith('/api/v1/households/1/rooms/3', {
      name: 'Dining',
      floor_id: null,
      sort_order: 1,
      slug: undefined,
      clear_slug: true,
    });
  });
});
