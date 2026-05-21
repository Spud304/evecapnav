import type { SystemSearchResult, ShipClass, CapShip, RouteResult, MapData } from './types';

export async function searchSystems(query: string): Promise<SystemSearchResult[]> {
  const resp = await fetch(`/api/systems/search?q=${encodeURIComponent(query)}`);
  return resp.json();
}

export async function getShipClasses(): Promise<ShipClass[]> {
  const resp = await fetch('/api/ship-classes');
  return resp.json();
}

export async function getCapShips(): Promise<CapShip[]> {
  const resp = await fetch('/api/cap-ships');
  return resp.json();
}

export async function getMapData(): Promise<MapData> {
  const resp = await fetch('/api/map/data');
  return resp.json();
}

export function planRouteSSE(
  params: {
    origin_id: number;
    destination_id: number;
    ship_class: string;
    jdc_level: number;
    jfc_level: number;
    initial_fatigue: number;
    mode: 'safe' | 'direct' | 'pos';
    avoid_alliances: string;
    base_system_cost: number;
    distance_exponent: number;
    danger_weight: number;
    jumps_weight: number;
    activity_weight: number;
    dead_end_penalty: number;
    pos_moon_bonus: number;
    wait_weight: number;
    gate_mode?: 'off' | 'interregional' | 'all';
    gate_equivalent_jumps?: number;
  },
  callbacks: {
    onProgress: (msg: string) => void;
    onResult: (result: RouteResult) => void;
    onError: (msg: string) => void;
  },
): EventSource {
  const qs = new URLSearchParams({
    origin_id: String(params.origin_id),
    destination_id: String(params.destination_id),
    ship_class: params.ship_class,
    jdc_level: String(params.jdc_level),
    jfc_level: String(params.jfc_level),
    initial_fatigue: String(params.initial_fatigue),
    mode: params.mode,
    avoid_alliances: params.avoid_alliances,
    base_system_cost: String(params.base_system_cost),
    distance_exponent: String(params.distance_exponent),
    danger_weight: String(params.danger_weight),
    jumps_weight: String(params.jumps_weight),
    activity_weight: String(params.activity_weight),
    dead_end_penalty: String(params.dead_end_penalty),
    pos_moon_bonus: String(params.pos_moon_bonus),
    wait_weight: String(params.wait_weight),
    gate_mode: params.gate_mode ?? 'off',
    gate_equivalent_jumps: String(params.gate_equivalent_jumps ?? 5),
  });

  const es = new EventSource(`/api/route?${qs}`);

  es.addEventListener('progress', (e) => {
    callbacks.onProgress(e.data.replace(/^"|"$/g, ''));
  });

  es.addEventListener('result', (e) => {
    es.close();
    callbacks.onResult(JSON.parse(e.data));
  });

  es.addEventListener('error', (e) => {
    es.close();
    if (e instanceof MessageEvent && e.data) {
      const parsed = JSON.parse(e.data);
      callbacks.onError(parsed.error || 'Unknown error');
    } else {
      callbacks.onError('Connection lost');
    }
  });

  return es;
}

export async function swapHop(params: {
  path: number[];
  hop: number;
  alt_id: number;
  ship_class: string;
  jdc_level: number;
  jfc_level: number;
  initial_fatigue: number;
  mode: string;
  base_system_cost: number;
  distance_exponent: number;
  danger_weight: number;
  jumps_weight: number;
  activity_weight: number;
  dead_end_penalty: number;
  pos_moon_bonus: number;
  wait_weight: number;
}): Promise<RouteResult> {
  const qs = new URLSearchParams({
    path: params.path.join(','),
    hop: String(params.hop),
    alt_id: String(params.alt_id),
    ship_class: params.ship_class,
    jdc_level: String(params.jdc_level),
    jfc_level: String(params.jfc_level),
    initial_fatigue: String(params.initial_fatigue),
    mode: params.mode,
    base_system_cost: String(params.base_system_cost),
    distance_exponent: String(params.distance_exponent),
    danger_weight: String(params.danger_weight),
    jumps_weight: String(params.jumps_weight),
    activity_weight: String(params.activity_weight),
    dead_end_penalty: String(params.dead_end_penalty),
    pos_moon_bonus: String(params.pos_moon_bonus),
    wait_weight: String(params.wait_weight),
  });
  const resp = await fetch(`/api/route/swap?${qs}`);
  return resp.json();
}
