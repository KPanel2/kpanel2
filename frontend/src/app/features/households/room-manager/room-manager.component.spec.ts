import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { RoomManagerComponent } from './room-manager.component';
import { HouseholdService } from '../../../core/services/household.service';
import { Household, Room } from '../../../core/models/household.model';

describe('RoomManagerComponent', () => {
  let fixture: ComponentFixture<RoomManagerComponent>;
  let component: RoomManagerComponent;
  let householdService: jasmine.SpyObj<HouseholdService>;

  const household: Household = {
    id: 1,
    name: 'Home',
    timezone: null,
    owner_id: 1,
    created_at: '',
    updated_at: '',
    floors: [{ id: 2, household_id: 1, name: 'Ground', sort_order: 0, created_at: '', updated_at: '' }],
    rooms: [
      {
        id: 3,
        household_id: 1,
        floor_id: 2,
        name: 'Kitchen',
        slug: 'kitchen',
        sort_order: 0,
        created_at: '',
        updated_at: '',
      },
    ],
    urls: [],
    members: [],
  };

  beforeEach(async () => {
    householdService = jasmine.createSpyObj<HouseholdService>('HouseholdService', [
      'createRoom',
      'updateRoom',
      'deleteRoom',
    ]);

    await TestBed.configureTestingModule({
      imports: [RoomManagerComponent],
      providers: [{ provide: HouseholdService, useValue: householdService }],
    }).compileComponents();

    fixture = TestBed.createComponent(RoomManagerComponent);
    component = fixture.componentInstance;
    component.household = household;
    fixture.detectChanges();
  });

  it('creates a room with an optional slug', () => {
    householdService.createRoom.and.returnValue(of({} as Room));
    spyOn(component.roomsChanged, 'emit');

    component.creating = true;
    component.newName = 'Office';
    component.newSlug = 'office';
    component.newFloorId = 2;
    component.newOrder = 1;
    component.create();

    expect(householdService.createRoom).toHaveBeenCalledWith(1, 'Office', 2, 1, 'office');
    expect(component.roomsChanged.emit).toHaveBeenCalled();
    expect(component.newSlug).toBe('');
  });

  it('clears slug when saving an empty edit value', () => {
    householdService.updateRoom.and.returnValue(of({} as Room));
    const room = household.rooms[0];

    component.startEdit(room);
    component.editSlug = '';
    component.saveEdit();

    expect(householdService.updateRoom).toHaveBeenCalledWith(
      1,
      3,
      'Kitchen',
      2,
      0,
      null,
      true
    );
  });

  it('surfaces create errors', () => {
    householdService.createRoom.and.returnValue(throwError(() => new Error('slug taken')));
    component.newName = 'Office';
    component.create();
    expect(component.error).toBe('slug taken');
  });
});
