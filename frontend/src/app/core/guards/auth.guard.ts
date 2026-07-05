import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { filter, map, switchMap, take } from 'rxjs/operators';

import { AuthService } from '../services/auth.service';

function waitForResolvedSession() {
  const auth = inject(AuthService);
  return auth.authReady$.pipe(
    filter(ready => ready),
    take(1),
    switchMap(() => auth.session$.pipe(take(1))),
  );
}

export const authGuard: CanActivateFn = () => {
  const router = inject(Router);
  return waitForResolvedSession().pipe(
    map(session => {
      if (session.status === 'authenticated') return true;
      return router.createUrlTree(['/login']);
    }),
  );
};

export const guestGuard: CanActivateFn = () => {
  const router = inject(Router);
  return waitForResolvedSession().pipe(
    map(session => {
      if (session.status === 'authenticated') return router.createUrlTree(['/']);
      return true;
    }),
  );
};
