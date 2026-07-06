import { decodeJwtPayload, scopeClaimToList } from './jwt-decode';

function encodePayload(payload: Record<string, unknown>): string {
  const json = JSON.stringify(payload);
  const b64 = btoa(json).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `header.${b64}.signature`;
}

describe('jwt-decode', () => {
  describe('decodeJwtPayload', () => {
    it('returns null for empty or missing tokens', () => {
      expect(decodeJwtPayload(null)).toBeNull();
      expect(decodeJwtPayload(undefined)).toBeNull();
      expect(decodeJwtPayload('')).toBeNull();
      expect(decodeJwtPayload('   ')).toBeNull();
    });

    it('returns null when the token has no payload segment', () => {
      expect(decodeJwtPayload('only-one-part')).toBeNull();
    });

    it('decodes a valid JWT payload', () => {
      const token = encodePayload({ sub: 'user-1', scope: 'openid email' });
      expect(decodeJwtPayload(token)).toEqual({ sub: 'user-1', scope: 'openid email' });
    });

    it('handles base64url padding', () => {
      const token = encodePayload({ exp: 9999999999 });
      expect(decodeJwtPayload(token)?.['exp']).toBe(9999999999);
    });

    it('returns null for invalid base64 or JSON', () => {
      expect(decodeJwtPayload('a.!!!invalid!!!.c')).toBeNull();
    });
  });

  describe('scopeClaimToList', () => {
    it('splits space-delimited scope strings', () => {
      expect(scopeClaimToList('kpanel:admin securityflags:fraud')).toEqual([
        'kpanel:admin',
        'securityflags:fraud',
      ]);
    });

    it('filters empty tokens from scope strings', () => {
      expect(scopeClaimToList('  kpanel:admin   ')).toEqual(['kpanel:admin']);
    });

    it('returns string items from arrays', () => {
      expect(scopeClaimToList(['a', 1, 'b', null])).toEqual(['a', 'b']);
    });

    it('returns an empty list for other types', () => {
      expect(scopeClaimToList(null)).toEqual([]);
      expect(scopeClaimToList(42)).toEqual([]);
    });
  });
});
