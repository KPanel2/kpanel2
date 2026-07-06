import {
  BLOCKING_SECURITY_FLAGS,
  findBlockingSecurityFlags,
  securityFlagDenialMessage,
} from './security-flags';

describe('security-flags', () => {
  describe('findBlockingSecurityFlags', () => {
    it('returns matching blocking flags from scopes', () => {
      const scopes = ['kpanel:admin', 'securityflags:fraud', 'other'];
      expect(findBlockingSecurityFlags(scopes)).toEqual(['securityflags:fraud']);
    });

    it('returns multiple blocking flags in definition order', () => {
      const scopes = ['securityflags:incarcerated', 'securityflags:fraud'];
      expect(findBlockingSecurityFlags(scopes)).toEqual([
        'securityflags:fraud',
        'securityflags:incarcerated',
      ]);
    });

    it('returns empty when no blocking flags are present', () => {
      expect(findBlockingSecurityFlags(['kpanel:admin'])).toEqual([]);
    });

    it('covers all blocking flag constants', () => {
      expect(findBlockingSecurityFlags([...BLOCKING_SECURITY_FLAGS])).toEqual([...BLOCKING_SECURITY_FLAGS]);
    });
  });

  describe('securityFlagDenialMessage', () => {
    it('returns a single flag message unchanged', () => {
      const message = securityFlagDenialMessage(['securityflags:fraud']);
      expect(message).toContain('fraud flag');
    });

    it('returns a single incarcerated flag message unchanged', () => {
      const message = securityFlagDenialMessage(['securityflags:incarcerated']);
      expect(message).toContain('incarcerated');
    });

    it('joins multiple flag messages', () => {
      const message = securityFlagDenialMessage(['securityflags:fraud', 'securityflags:mechid']);
      expect(message).toContain('fraud flag');
      expect(message).toContain('machine');
    });

    it('ignores unknown flags', () => {
      expect(securityFlagDenialMessage(['unknown:flag'])).toBe('');
    });
  });
});
