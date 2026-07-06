import { Injector } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { OidcSecurityService } from 'angular-auth-oidc-client';

import { OidcRuntimeService } from './oidc-runtime.service';
import { environment } from '../../../environments/environment';

describe('OidcRuntimeService', () => {
  let service: OidcRuntimeService;
  let originalAppId: string;

  beforeEach(() => {
    originalAppId = environment.logto.appId;
  });

  afterEach(() => {
    environment.logto.appId = originalAppId;
  });

  function configure(injectorGet: jasmine.Spy) {
    TestBed.configureTestingModule({
      providers: [
        OidcRuntimeService,
        { provide: Injector, useValue: { get: injectorGet } },
      ],
    });
    service = TestBed.inject(OidcRuntimeService);
  }

  it('reports unavailable when OIDC is not configured', () => {
    environment.logto.appId = '';
    configure(jasmine.createSpy('get'));

    expect(service.available).toBeFalse();
    expect(service.getService()).toBeNull();
  });

  it('returns null when OIDC is configured but service is missing', () => {
    environment.logto.appId = 'configured-app';
    configure(jasmine.createSpy('get').and.throwError('No provider'));

    expect(service.available).toBeTrue();
    expect(service.getService()).toBeNull();
    expect(service.getService()).toBeNull();
  });

  it('caches the resolved OIDC service', () => {
    environment.logto.appId = 'configured-app';
    const oidc = {} as OidcSecurityService;
    const injectorGet = jasmine.createSpy('get').and.returnValue(oidc);
    configure(injectorGet);

    expect(service.getService()).toBe(oidc);
    expect(service.getService()).toBe(oidc);
    expect(injectorGet).toHaveBeenCalledTimes(1);
  });
});
