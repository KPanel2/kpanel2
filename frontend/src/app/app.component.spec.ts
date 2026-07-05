import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';

import { AppComponent } from './app.component';
import { AuthService } from './core/services/auth.service';
import { AuthFlowService } from './core/services/auth-flow.service';
import { SessionState } from './core/models/session.model';

describe('AppComponent', () => {
  let session$: BehaviorSubject<SessionState>;
  let authReady$: BehaviorSubject<boolean>;
  let navigateSpy: jasmine.Spy;
  let bootstrapSpy: jasmine.Spy;

  beforeEach(async () => {
    session$ = new BehaviorSubject<SessionState>({ status: 'unauthenticated', permissions: [] });
    authReady$ = new BehaviorSubject(false);
    navigateSpy = jasmine.createSpy('navigate');
    bootstrapSpy = jasmine.createSpy('bootstrapApp').and.returnValue(of({ status: 'unauthenticated', permissions: [] }));

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        AuthFlowService,
        {
          provide: AuthService,
          useValue: {
            session$,
            authReady$,
            get authReady() {
              return authReady$.value;
            },
            consumeAccountCenterSuccess: () => false,
            bootstrapApp: bootstrapSpy,
          },
        },
        {
          provide: Router,
          useValue: {
            url: '/login',
            navigate: navigateSpy,
          },
        },
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('bootstraps auth on startup', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    expect(bootstrapSpy).toHaveBeenCalledWith({ refreshClaims: false });
  });

  it('does not route away from login before bootstrap completes', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    navigateSpy.calls.reset();

    session$.next({ status: 'authenticated', permissions: [] });
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it('routes authenticated users away from login after bootstrap', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    navigateSpy.calls.reset();

    authReady$.next(true);
    session$.next({ status: 'authenticated', permissions: [] });

    expect(navigateSpy).toHaveBeenCalledWith(['/']);
  });
});
