export function decodeJwtPayload(token: string | null | undefined): Record<string, unknown> | null {
  if (!token?.trim()) {
    return null;
  }

  const parts = token.trim().split('.');
  if (parts.length < 2) {
    return null;
  }

  try {
    const padded = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(padded.padEnd(padded.length + ((4 - padded.length % 4) % 4), '='));
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function scopeClaimToList(scope: unknown): string[] {
  if (typeof scope === 'string') {
    return scope.split(/\s+/).filter(Boolean);
  }
  if (Array.isArray(scope)) {
    return scope.filter((item): item is string => typeof item === 'string');
  }
  return [];
}
