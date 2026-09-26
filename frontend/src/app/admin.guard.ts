import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AdminAuthService } from './admin-auth.service';

export const adminGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AdminAuthService);
  const router = inject(Router);
  return auth.checkSession().pipe(
    map((authenticated) => authenticated || router.createUrlTree(['/login'], {
      queryParams: { returnUrl: state.url }
    }))
  );
};