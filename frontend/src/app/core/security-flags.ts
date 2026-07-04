export const BLOCKING_SECURITY_FLAGS = [
  'securityflags:fraud',
  'securityflags:mechid',
  'securityflags:incarcerated',
] as const;

export const SECURITY_FLAG_DENIAL_MESSAGES: Record<string, string> = {
  'securityflags:fraud': 'Access to kPanel is not permitted due to a fraud flag on your account.',
  'securityflags:mechid':
    'This account is registered as a machine, not a human. kPanel is for people only — bots, scripts, and vending machines need not apply.',
  'securityflags:incarcerated': 'Access to kPanel is not available for persons currently incarcerated.',
};

export function findBlockingSecurityFlags(scopes: string[]): string[] {
  return BLOCKING_SECURITY_FLAGS.filter(flag => scopes.includes(flag));
}

export function securityFlagDenialMessage(flags: string[]): string {
  const messages = flags.map(flag => SECURITY_FLAG_DENIAL_MESSAGES[flag]).filter(Boolean);
  if (messages.length === 1) {
    return messages[0];
  }
  return messages.join(' ');
}
