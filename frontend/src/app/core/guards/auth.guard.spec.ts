import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { BehaviorSubject, isObservable } from 'rxjs';
import { firstValueFrom } from 'rxjs';

import { authGuard, guestGuard } from './auth.guard';
import { AuthService } from '../services/auth.service';
import { SessionState } from '../models/session.model';

describe('auth guards', () => {
  let session$: BehaviorSubject<SessionState>;
  let authReady$: BehaviorSubject<boolean>;
  let router: Router;

  beforeEach(() => {
    session$ = new BehaviorSubject<SessionState>({ status: 'unauthenticated', permissions: [] });
    authReady$ = new BehaviorSubject(false);

    TestBed.configureTestingModule({
      providers: [
        {
          provide: AuthService,
          useValue: { session$, authReady$ },
        },
      ],
    });

    router = TestBed.inject(Router);
  });

  async function runGuard(guard: typeof authGuard) {
    const result = TestBed.runInInjectionContext(() => guard({} as never, {} as never));
    if (isObservable(result)) {
      return firstValueFrom(result);
    }
    return result;
  }

  describe('authGuard', () => {
    it('allows authenticated users after bootstrap', async () => {
      session$.next({ status: 'authenticated', permissions: [] });
      authReady$.next(true);

      await expectAsync(runGuard(authGuard)).toBeResolvedTo(true);
    });

    it('redirects unauthenticated users to login', async () => {
      session$.next({ status: 'unauthenticated', permissions: [] });
      authReady$.next(true);

      await expectAsync(runGuard(authGuard)).toBeResolvedTo(router.createUrlTree(['/login']));
    });
  });

  describe('guestGuard', () => {
    it('allows unauthenticated guests', async () => {
      session$.next({ status: 'unauthenticated', permissions: [] });
      authReady$.next(true);

      await expectAsync(runGuard(guestGuard)).toBeResolvedTo(true);
    });

    it('redirects authenticated users to home', async () => {
      session$.next({ status: 'authenticated', permissions: [] });
      authReady$.next(true);

      await expectAsync(runGuard(guestGuard)).toBeResolvedTo(router.createUrlTree(['/']));
    });
  });
});
