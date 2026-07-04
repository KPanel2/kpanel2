export interface Identity {
  provider_name: string;
  email: string | null;
  display_name: string | null;
}

export interface Device {
  registration_code: string;
  device_id: string | null;
  display_name: string | null;
  target_url: string | null;
  room_id: number | null;
  url_mode: string | null;
  household_url_id: number | null;
  has_temp_url: boolean;
  temp_url: string | null;
  temp_url_revert_mode: string | null;
  temp_url_revert_household_url_id: number | null;
  temp_url_set_at: string | null;
  resolved_url: string | null;
  timezone: string | null;
  client_version: string | null;
  latest_client_version: string | null;
  registered_at: string;
  last_seen: string | null;
}

export interface User {
  id: number;
  email: string;
  display_name: string;
  timezone: string;
  identities: Identity[];
  devices: Device[];
}

export interface PendingAuth {
  provider_name: string;
  email: string | null;
  display_name?: string | null;
}

export interface SessionState {
  status: 'unauthenticated' | 'needs_account' | 'authenticated' | 'access_denied';
  permissions: string[];
  user?: User;
  pending?: PendingAuth;
  message?: string;
  /** Present when KPANEL_AUTH_DEBUG_ENABLED — server-side security-flag evaluation. */
  debug?: Record<string, unknown>;
}
