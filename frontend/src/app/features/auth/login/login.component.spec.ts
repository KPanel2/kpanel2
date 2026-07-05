import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { LoginComponent } from './login.component';
import { AuthService } from '../../../core/services/auth.service';
import { AuthFlowService } from '../../../core/services/auth-flow.service';
import { SessionState } from '../../../core/models/session.model';
import { environment } from '../../../../environments/environment';

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let component: LoginComponent;
  let session$: BehaviorSubject<SessionState>;
  let authReady$: BehaviorSubject<boolean>;
  let signInSpy: jasmine.Spy;
  let navigateSpy: jasmine.Spy;
  let originalAppId: string;
  let originalDevAuthEnabled: boolean;

  const UNAUTHENTICATED: SessionState = { status: 'unauthenticated', permissions: [] };

  beforeEach(async () => {
    originalAppId = environment.logto.appId;
    originalDevAuthEnabled = environment.devAuthEnabled;
    environment.logto.appId = 'test-app-id';
    environment.devAuthEnabled = false;

    session$ = new BehaviorSubject<SessionState>(UNAUTHENTICATED);
    authReady$ = new BehaviorSubject(false);
    signInSpy = jasmine.createSpy('signIn').and.returnValue(Promise.resolve());
    navigateSpy = jasmine.createSpy('navigate');

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        AuthFlowService,
        {
          provide: AuthService,
          useValue: {
            session$,
            authReady$,
            signIn: signInSpy,
            logout: jasmine.createSpy('logout'),
            loadSession: jasmine.createSpy('loadSession').and.returnValue({ subscribe: () => undefined }),
            createAccount: jasmine.createSpy('createAccount'),
            accountCenterProfileUrl: () => 'https://account.example/profile',
          },
        },
        {
          provide: Router,
          useValue: { navigate: navigateSpy },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => {
    environment.logto.appId = originalAppId;
    environment.devAuthEnabled = originalDevAuthEnabled;
  });

  function detect() {
    fixture.detectChanges();
  }

  it('shows checking UI during bootstrap', () => {
    detect();
    expect(component.viewPhase).toBe('checking');
    expect(fixture.nativeElement.querySelector('app-auth-status')?.textContent)
      .toContain('Checking sign-in…');
    expect(fixture.nativeElement.querySelector('.provider-button')).toBeNull();
  });

  it('auto-redirects to KumpeCloud when unauthenticated with OIDC configured', () => {
    detect();
    authReady$.next(true);
    detect();

    expect(signInSpy).toHaveBeenCalled();
    expect(component.viewPhase).toBe('redirecting');
    expect(fixture.nativeElement.textContent).toContain('Redirecting to KumpeCloud…');
  });

  it('does not auto-redirect for access_denied', () => {
    detect();
    session$.next({ status: 'access_denied', permissions: [], message: 'Denied' });
    authReady$.next(true);
    detect();

    expect(signInSpy).not.toHaveBeenCalled();
    expect(component.viewPhase).toBe('access_denied');
    expect(fixture.nativeElement.textContent).toContain('Access Not Permitted');
  });

  it('does not auto-redirect for needs_account', () => {
    detect();
    session$.next({
      status: 'needs_account',
      permissions: [],
      pending: { provider_name: 'logto', email: 'user@example.com' },
    });
    authReady$.next(true);
    detect();

    expect(signInSpy).not.toHaveBeenCalled();
    expect(component.viewPhase).toBe('needs_account');
    expect(fixture.nativeElement.textContent).toContain('Create Account');
  });

  it('shows dev sign-in form when dev auth is enabled without OIDC', () => {
    environment.logto.appId = '';
    environment.devAuthEnabled = true;

    detect();
    authReady$.next(true);
    detect();

    expect(signInSpy).not.toHaveBeenCalled();
    expect(component.viewPhase).toBe('dev_sign_in');
    expect(fixture.nativeElement.querySelector('.dev-login-form')).not.toBeNull();
  });

  it('does not flash manual login UI after authentication', () => {
    detect();
    session$.next({ status: 'authenticated', permissions: [] });
    authReady$.next(true);
    detect();

    expect(component.viewPhase).toBe('checking');
    expect(fixture.nativeElement.querySelector('.provider-button')).toBeNull();
    expect(navigateSpy).toHaveBeenCalledWith(['/']);
  });

  it('shows retry action after auto-redirect failure', async () => {
    signInSpy.and.returnValue(Promise.reject(new Error('Redirect failed')));

    detect();
    authReady$.next(true);
    detect();
    await fixture.whenStable();
    detect();

    expect(component.viewPhase).toBe('oidc_fallback');
    expect(fixture.nativeElement.textContent).toContain('Redirect failed');
    expect(fixture.nativeElement.textContent).toContain('Try again');
  });
});
