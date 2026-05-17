export interface RouteStep {
  system_id: number;
  system_name: string;
  security: number;
  distance_ly: number;
  wait_minutes: number;
  fatigue_after_minutes: number;
  fuel_cost: number;
  kills_per_hour: number;
  jumps_per_hour: number;
  safe_spot_au: number;
  safe_spot_warp: string;
  safe_spot_nearest: string;
  moon_count: number;
  gate_count: number;
  sov_owner: string;
  edge_type?: string;
}

export interface OptimizedRoute {
  steps: RouteStep[];
  extra_wait_minutes: number;
  total_fuel: number;
  total_wait_minutes: number;
}

export interface ZkillSystemStats {
  hourly_activity?: number[];
  active_characters?: number;
  active_corps?: number;
  gang_ratio?: string;
  ships_destroyed?: number;
}

export interface AlternativeSystem {
  id: number;
  name: string;
  distance_ly: number;
  security: number;
  sov_owner: string;
  moon_count: number;
  safe_spot_au: number;
}

export interface RouteResult {
  steps: RouteStep[];
  total_jumps: number;
  total_gate_hops?: number;
  total_fuel: number;
  total_wait_minutes: number;
  optimized?: OptimizedRoute;
  zkill?: Record<number, ZkillSystemStats>;
  quiet_hours?: { start: number; end: number };
  alternatives?: Record<string, AlternativeSystem[]>;
  jump_data_window?: '1h' | '24h';
  error?: string;
}

export interface ShipClass {
  label: string;
  base_range_ly: number;
  fatigue_multiplier: number;
  max_range_ly: number;
}

export interface SystemSearchResult {
  id: number;
  name: string;
  security: number;
}