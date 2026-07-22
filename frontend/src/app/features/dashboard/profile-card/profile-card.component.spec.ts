import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { ProfileCardComponent } from './profile-card.component';
import { AuthService } from '../../../core/services/auth.service';
import { User } from '../../../core/models/session.model';

describe('ProfileCardComponent', () => {
  let fixture: ComponentFixture<ProfileCardComponent>;
  let component: ProfileCardComponent;
  let auth: jasmine.SpyObj<AuthService>;

  const user: User = {
    id: 1,
    email: 'owner@example.com',
    display_name: 'Owner',
    timezone: 'America/Chicago',
    ha_bootstrap_url: null,
    has_ha_binding: false,
    identities: [],
    devices: [],
  };

  beforeEach(async () => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', [
      'accountCenterProfileUrl',
      'accountCenterEmailUrl',
      'accountCenterSecurityUrl',
      'takeAccountCenterSuccessKey',
      'updateHaBinding',
    ]);
    auth.accountCenterProfileUrl.and.returnValue('https://auth.example/profile');
    auth.accountCenterEmailUrl.and.returnValue('https://auth.example/email');
    auth.accountCenterSecurityUrl.and.returnValue('https://auth.example/security');
    auth.takeAccountCenterSuccessKey.and.returnValue(null);
    auth.updateHaBinding.and.returnValue(of({
      status: 'authenticated',
      permissions: [],
      user: { ...user, has_ha_binding: true, ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap' },
    }));

    await TestBed.configureTestingModule({
      imports: [ProfileCardComponent],
      providers: [{ provide: AuthService, useValue: auth }],
    }).compileComponents();

    fixture = TestBed.createComponent(ProfileCardComponent);
    component = fixture.componentInstance;
    component.user = { ...user };
    fixture.detectChanges();
  });

  it('saves account HA binding', () => {
    component.haBootstrapUrl = 'https://ha.example/api/kpanel_dashboard/bootstrap';
    component.haBindingSecret = 'account-secret';
    component.saveHaBinding();

    expect(auth.updateHaBinding).toHaveBeenCalledWith({
      ha_bootstrap_url: 'https://ha.example/api/kpanel_dashboard/bootstrap',
      ha_binding_secret: 'account-secret',
    });
  });

  it('clears account HA binding', () => {
    component.user = { ...user, has_ha_binding: true };
    component.clearHaBinding = true;
    component.saveHaBinding();

    expect(auth.updateHaBinding).toHaveBeenCalledWith({ clear_ha_binding: true });
  });

  it('requires input when not clearing', () => {
    component.saveHaBinding();
    expect(auth.updateHaBinding).not.toHaveBeenCalled();
    expect(component.error).toContain('bootstrap URL');
  });

  it('surfaces save errors', () => {
    auth.updateHaBinding.and.returnValue(throwError(() => new Error('denied')));
    component.haBootstrapUrl = 'https://ha.example/api/kpanel_dashboard/bootstrap';
    component.haBindingSecret = 'secret';
    component.saveHaBinding();
    expect(component.error).toBe('denied');
  });
});
