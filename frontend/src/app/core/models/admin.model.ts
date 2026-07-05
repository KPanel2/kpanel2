export interface AdminUserSummary {
  id: number;
  email: string;
  display_name: string;
  timezone: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  device_count: number;
  household_count: number;
  owned_household_count: number;
}

export interface AdminUserDetail {
  user: AdminUserSummary;
  identities: { id: number; provider_name: string; email: string; display_name: string }[];
  devices: AdminDevice[];
  households: { household_id: number; name: string; role: string; is_owner: boolean }[];
}

export interface AdminOwnerBrief {
  id: number;
  email: string;
  display_name: string;
}

export interface AdminHouseholdSummary {
  id: number;
  name: string;
  timezone: string | null;
  owner_id: number;
  owner: AdminOwnerBrief | null;
  member_count: number;
  url_count: number;
  device_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface AdminDevice {
  registration_code: string;
  device_id: string | null;
  display_name: string | null;
  target_url: string | null;
  timezone: string | null;
  room_id: number | null;
  url_mode: string | null;
  household_url_id: number | null;
  owner: AdminOwnerBrief | null;
  resolved_url?: string | null;
}

export interface AdminUrl {
  id: number;
  household_id: number;
  friendly_name: string;
  url_template: string;
  is_default: boolean;
  household_name: string | null;
  owner: AdminOwnerBrief | null;
}

export interface AdminOverview {
  users: number;
  active_users: number;
  households: number;
  devices: number;
  claimed_devices: number;
  household_urls: number;
}
