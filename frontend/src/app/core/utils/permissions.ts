import { SessionState } from '../models/session.model';

export const PERMISSION_SUPERADMIN = 'kpanel:superadmin';
export const PERMISSION_ADMIN = 'kpanel:admin';

export function sessionPermissions(session: SessionState | null | undefined): string[] {
  return session?.permissions ?? [];
}

export function hasPermission(
  session: SessionState | null | undefined,
  permission: string,
): boolean {
  const permissions = sessionPermissions(session);
  return permissions.includes(PERMISSION_ADMIN) || permissions.includes(permission);
}

export function isSuperadmin(session: SessionState | null | undefined): boolean {
  return sessionPermissions(session).includes(PERMISSION_SUPERADMIN);
}
