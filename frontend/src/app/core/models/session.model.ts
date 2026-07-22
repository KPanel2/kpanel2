export interface Identity {
  provider_name: string;
  email: string | null;
  display_name: string | null;
}

export type HaBindingSource = 'device' | 'room' | 'household' | 'account';

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
  ha_bootstrap_url: string | null;
  has_ha_binding: boolean;
  has_local_ha_binding?: boolean;
  ha_binding_source?: HaBindingSource | null;
  effective_ha_bootstrap_url?: string | null;
}

export interface User {
  id: number;
  email: string;
  display_name: string;
  timezone: string;
  ha_bootstrap_url?: string | null;
  has_ha_binding?: boolean;
  identities: Identity[];
  devices: Device[];
}

export interface PendingAuth {
  provider_name: string;
  email: string | null;
  display_name?: string | null;
  timezone?: string | null;
}

export interface SessionState {
  status: 'unauthenticated' | 'needs_account' | 'authenticated' | 'access_denied';
  permissions: string[];
  user?: User;
  pending?: PendingAuth;
  message?: string;
}

export interface HaBindingUpdate {
  ha_bootstrap_url?: string | null;
  ha_binding_secret?: string | null;
  clear_ha_binding?: boolean;
}
