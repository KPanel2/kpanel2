import { SessionState } from '../models/session.model';
import {
  PERMISSION_ADMIN,
  PERMISSION_SUPERADMIN,
  hasPermission,
  isSuperadmin,
  sessionPermissions,
} from './permissions';

const AUTHENTICATED = (permissions: string[]): SessionState => ({
  status: 'authenticated',
  permissions,
});

describe('permissions', () => {
  describe('sessionPermissions', () => {
    it('returns permissions from session', () => {
      expect(sessionPermissions(AUTHENTICATED(['kpanel:admin']))).toEqual(['kpanel:admin']);
    });

    it('returns empty array for nullish session', () => {
      expect(sessionPermissions(null)).toEqual([]);
      expect(sessionPermissions(undefined)).toEqual([]);
    });
  });

  describe('hasPermission', () => {
    it('grants admin users any permission', () => {
      expect(hasPermission(AUTHENTICATED([PERMISSION_ADMIN]), 'kpanel:devices')).toBeTrue();
    });

    it('grants explicit permission when present', () => {
      expect(hasPermission(AUTHENTICATED(['kpanel:devices']), 'kpanel:devices')).toBeTrue();
    });

    it('denies missing permission for non-admin users', () => {
      expect(hasPermission(AUTHENTICATED(['kpanel:read']), 'kpanel:devices')).toBeFalse();
    });
  });

  describe('isSuperadmin', () => {
    it('detects superadmin permission', () => {
      expect(isSuperadmin(AUTHENTICATED([PERMISSION_SUPERADMIN]))).toBeTrue();
      expect(isSuperadmin(AUTHENTICATED([PERMISSION_ADMIN]))).toBeFalse();
    });
  });
});
