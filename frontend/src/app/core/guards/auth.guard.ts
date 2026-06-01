import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map, take } from 'rxjs/operators';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.session$.pipe(
    take(1),
    map(session => {
      if (session?.status === 'authenticated') return true;
      return router.createUrlTree(['/login']);
    })
  );
};

export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.session$.pipe(
    take(1),
    map(session => {
      if (session?.status === 'authenticated') return router.createUrlTree(['/']);
      return true;
    })
  );
};
