export interface Floor {
  id: number;
  household_id: number;
  name: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Room {
  id: number;
  household_id: number;
  floor_id: number | null;
  name: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface HouseholdUrl {
  id: number;
  household_id: number;
  friendly_name: string;
  url_template: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface Member {
  user_id: number;
  role: string;
  email: string;
  display_name: string;
  joined_at: string;
}

export interface Household {
  id: number;
  name: string;
  timezone: string | null;
  owner_id: number;
  created_at: string;
  updated_at: string;
  floors: Floor[];
  rooms: Room[];
  urls: HouseholdUrl[];
  members: Member[];
}
