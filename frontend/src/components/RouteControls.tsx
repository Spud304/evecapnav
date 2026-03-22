import { useState, useEffect, useRef } from 'react';
import SystemSearch from './SystemSearch';
import { getShipClasses, planRouteSSE } from '../api';
import type { ShipClass, RouteResult } from '../types';

export interface RouteParams {
  ship_class: string;
  jdc_level: number;
  jfc_level: number;
  initial_fatigue: number;
  mode: string;
}

interface Props {
  onResult: (result: RouteResult, params: RouteParams) => void;
  onError: (msg: string) => void;
  onProgress: (msg: string) => void;
}

export default function RouteControls({ onResult, onError, onProgress }: Props) {
  const [shipClasses, setShipClasses] = useState<ShipClass[]>([]);
  const [originId, setOriginId] = useState<number | null>(null);
  const [destId, setDestId] = useState<number | null>(null);
  const [shipClass, setShipClass] = useState('');
  const [jdc, setJdc] = useState(5);
  const [jfc, setJfc] = useState(4);
  const [fatigue, setFatigue] = useState(0);
  const [mode, setMode] = useState<'safe' | 'direct' | 'pos'>('safe');
  const [avoidAlliances, setAvoidAlliances] = useState('');
  const [loading, setLoading] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    getShipClasses().then((classes) => {
      setShipClasses(classes);
      if (classes.length > 0) setShipClass(classes[0].label);
    });
  }, []);

  function handlePlan() {
    if (!originId || !destId) {
      onError('Please select both origin and destination systems.');
      return;
    }

    esRef.current?.close();

    setLoading(true);
    onProgress('Connecting...');

    esRef.current = planRouteSSE(
      {
        origin_id: originId,
        destination_id: destId,
        ship_class: shipClass,
        jdc_level: jdc,
        jfc_level: jfc,
        initial_fatigue: fatigue,
        mode,
        avoid_alliances: avoidAlliances,
      },
      {
        onProgress: (msg) => onProgress(msg),
        onResult: (result) => {
          setLoading(false);
          if (result.error && !result.steps?.length) {
            onError(result.error);
          } else {
            onResult(result, {
              ship_class: shipClass,
              jdc_level: jdc,
              jfc_level: jfc,
              initial_fatigue: fatigue,
              mode,
            });
          }
        },
        onError: (msg) => {
          setLoading(false);
          onError(msg);
        },
      },
    );
  }

  return (
    <div className="bg-[#16213e] border border-[#0f3460] rounded-lg p-4 mb-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        <SystemSearch
          label="Origin System"
          onSelect={(id) => setOriginId(id)}
        />
        <SystemSearch
          label="Destination System"
          onSelect={(id) => setDestId(id)}
        />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
        <div>
          <label className="block text-sm mb-1 text-gray-300">Ship Class</label>
          <select
            value={shipClass}
            onChange={(e) => setShipClass(e.target.value)}
            className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-gray-200"
          >
            {shipClasses.map((c) => (
              <option key={c.label} value={c.label}>
                {c.label} ({c.base_range_ly} LY)
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1 text-gray-300">JDC Level</label>
          <select
            value={jdc}
            onChange={(e) => setJdc(Number(e.target.value))}
            className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-gray-200"
          >
            {[0, 1, 2, 3, 4, 5].map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1 text-gray-300">JFC Level</label>
          <select
            value={jfc}
            onChange={(e) => setJfc(Number(e.target.value))}
            className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-gray-200"
          >
            {[0, 1, 2, 3, 4, 5].map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1 text-gray-300">Routing Mode</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as 'safe' | 'direct' | 'pos')}
            className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-gray-200"
          >
            <option value="safe">Safe (avoid danger)</option>
            <option value="direct">Direct (shortest path)</option>
            <option value="pos">POS Hopping (prefer moons)</option>
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1 text-gray-300">
            Fatigue (min)
          </label>
          <input
            type="number"
            value={fatigue}
            onChange={(e) => setFatigue(Number(e.target.value))}
            min={0}
            max={720}
            className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-gray-200"
          />
        </div>
        <button
          onClick={handlePlan}
          disabled={loading}
          className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium"
        >
          {loading ? 'Planning...' : 'Plan Route'}
        </button>
      </div>
      <div className="mt-3">
        <label className="block text-sm mb-1 text-gray-300">
          Avoid Alliances <span className="text-gray-500">(comma-separated names)</span>
        </label>
        <input
          type="text"
          value={avoidAlliances}
          onChange={(e) => setAvoidAlliances(e.target.value)}
          placeholder="e.g. Goonswarm Federation, Pandemic Horde"
          className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-gray-200"
        />
      </div>
    </div>
  );
}
