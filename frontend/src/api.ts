import type { SystemSearchResult, ShipClass, RouteResult } from './types';

export async function searchSystems(query: string): Promise<SystemSearchResult[]> {
  const resp = await fetch(`/api/systems/search?q=${encodeURIComponent(query)}`);
  return resp.json();
}

export async function getShipClasses(): Promise<ShipClass[]> {
  const resp = await fetch('/api/ship-classes');
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
  });
  const resp = await fetch(`/api/route/swap?${qs}`);
  return resp.json();
}
