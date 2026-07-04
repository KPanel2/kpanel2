export function normalizeLogtoResource(resource: string): string {
  return resource.trim().replace(/\/+$/, '');
}

export function isInvalidTargetError(message: string): boolean {
  return message.includes('invalid_target') || message.includes('oidc.invalid_target');
}

export function isInvalidScopeError(message: string): boolean {
  return message.includes('invalid_scope') || message.includes('oidc.invalid_scope');
}

export function parseLogtoTokenError(message: string): string {
  try {
    const parsed = JSON.parse(message) as {
      code?: string;
      error?: string;
      message?: string;
      error_description?: string;
    };

    if (parsed.code === 'oidc.invalid_target' || parsed.error === 'invalid_target') {
      return [
        'KumpeCloud Auth rejected the API resource indicator.',
        'Verify apiResource matches KumpeCloud Console → API Resources exactly.',
        'Sign out and sign in again after permission changes.',
      ].join(' ');
    }

    if (parsed.error === 'invalid_grant' || parsed.code === 'oidc.invalid_grant') {
      return 'Your KumpeCloud session expired. Sign out and sign in again.';
    }

    if (parsed.code === 'oidc.invalid_scope' || parsed.error === 'invalid_scope') {
      if (parsed.error_description?.includes('refresh token missing requested scopes')) {
        return [
          'KumpeCloud Auth did not grant the requested API permissions during sign-in.',
          'Sign out completely, then sign in again so kpanel:* scopes are consented.',
          'Verify your role includes the API permissions in KumpeCloud Console.',
        ].join(' ');
      }

      return [
        'KumpeCloud Auth rejected the requested API permissions.',
        'Verify kpanel:* scopes exist on the API resource and are assigned to your role.',
      ].join(' ');
    }

    return parsed.message ?? parsed.error_description ?? message;
  } catch {
    return message;
  }
}
