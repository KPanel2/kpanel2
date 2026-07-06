import {
  isInvalidScopeError,
  isInvalidTargetError,
  normalizeLogtoResource,
  parseLogtoTokenError,
} from './logto-resource';

describe('logto-resource', () => {
  describe('normalizeLogtoResource', () => {
    it('trims whitespace and trailing slashes', () => {
      expect(normalizeLogtoResource('  https://api.example.com/  ')).toBe('https://api.example.com');
    });
  });

  describe('isInvalidTargetError', () => {
    it('detects invalid_target errors', () => {
      expect(isInvalidTargetError('oidc.invalid_target')).toBeTrue();
      expect(isInvalidTargetError('error: invalid_target')).toBeTrue();
      expect(isInvalidTargetError('other')).toBeFalse();
    });
  });

  describe('isInvalidScopeError', () => {
    it('detects invalid_scope errors', () => {
      expect(isInvalidScopeError('oidc.invalid_scope')).toBeTrue();
      expect(isInvalidScopeError('error: invalid_scope')).toBeTrue();
      expect(isInvalidScopeError('other')).toBeFalse();
    });
  });

  describe('parseLogtoTokenError', () => {
    it('returns invalid_target guidance', () => {
      const message = parseLogtoTokenError(JSON.stringify({ code: 'oidc.invalid_target' }));
      expect(message).toContain('API resource indicator');
    });

    it('returns invalid_target guidance for error field', () => {
      const message = parseLogtoTokenError(JSON.stringify({ error: 'invalid_target' }));
      expect(message).toContain('API resource indicator');
    });

    it('returns invalid_grant session expiry message', () => {
      const message = parseLogtoTokenError(JSON.stringify({ error: 'invalid_grant' }));
      expect(message).toContain('session expired');
    });

    it('returns invalid_grant session expiry message from code field', () => {
      const message = parseLogtoTokenError(JSON.stringify({ code: 'oidc.invalid_grant' }));
      expect(message).toContain('session expired');
    });

    it('returns refresh-scope guidance for invalid_scope with refresh token detail', () => {
      const message = parseLogtoTokenError(JSON.stringify({
        code: 'oidc.invalid_scope',
        error_description: 'refresh token missing requested scopes',
      }));
      expect(message).toContain('API permissions during sign-in');
    });

    it('returns generic invalid_scope guidance', () => {
      const message = parseLogtoTokenError(JSON.stringify({ error: 'invalid_scope' }));
      expect(message).toContain('rejected the requested API permissions');
    });

    it('falls back to message or error_description', () => {
      expect(parseLogtoTokenError(JSON.stringify({ message: 'Custom error' }))).toBe('Custom error');
      expect(parseLogtoTokenError(JSON.stringify({ error_description: 'Described' }))).toBe('Described');
    });

    it('returns the raw message when JSON parsing fails', () => {
      expect(parseLogtoTokenError('not-json')).toBe('not-json');
    });
  });
});
