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
  hourly_jumps?: number[]; // 24 floats, UTC index 0=00:00, weekly mean
  wait_cooldown_minutes?: number;
  wait_decay_minutes?: number;
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
  quiet_jumps?: { start: number; end: number; hourly: number[] };
  alternatives?: Record<string, AlternativeSystem[]>;
  risk_score?: number;
  risk_breakdown?: {
    kills: number;
    peak_jumps: number;
    dead_ends: number;
    hostile_systems: number;
  };
  total_fuel_isk?: number;
  error?: string;
}

export interface ShipClass {
  label: string;
  base_range_ly: number;
  fatigue_multiplier: number;
  max_range_ly: number;
}

export interface CapShip {
  type_id: number;
  type_name: string;
  group_id: number;
  class_label: string;
  base_range_ly: number;
  fuel_per_ly: number;
  fatigue_multiplier: number;
}

export interface SystemSearchResult {
  id: number;
  name: string;
  security: number;
}

export interface MapSystem {
  id: number;
  name: string;
  x: number;
  y: number;
  sec: number;
  region_id: number;
  sov: string;
}

export interface MapRegion {
  id: number;
  name: string;
  x: number;
  y: number;
  system_count: number;
}

export interface MapData {
  systems: MapSystem[];
  regions: MapRegion[];
  // gate edges as flat tuples [src_id, dst_id, cross_region (0|1)]
  gate_edges: [number, number, number][];
}