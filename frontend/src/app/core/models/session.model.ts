export interface Provider {
  name: string;
  label: string;
}

export interface Identity {
  provider_name: string;
  provider_user_id: string;
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
  link_providers?: string[];
}

export interface SessionState {
  status: 'unauthenticated' | 'needs_account' | 'needs_link' | 'link_ready' | 'authenticated';
  providers: Provider[];
  user?: User;
  pending?: PendingAuth;
  message?: string;
}
