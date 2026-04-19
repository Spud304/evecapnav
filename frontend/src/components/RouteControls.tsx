import { useState, useEffect, useRef } from 'react';
import SystemSearch from './SystemSearch';
import { getShipClasses, planRouteSSE } from '../api';
import type { ShipClass, RouteResult } from '../types';

const DEFAULT_WEIGHTS = {
  base_system_cost: 200,
  distance_exponent: 1.5,
  danger_weight: 600,
  jumps_weight: 60,
  dead_end_bonus: 100,
  pos_moon_bonus: 5,
};

export interface RouteParams {
  ship_class: string;
  jdc_level: number;
  jfc_level: number;
  jf_skill: number;
  initial_fatigue: number;
  mode: string;
  base_system_cost: number;
  distance_exponent: number;
  danger_weight: number;
  jumps_weight: number;
  dead_end_bonus: number;
  pos_moon_bonus: number;
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
  const [jfSkill, setJfSkill] = useState(4);
  const [avoidAlliances, setAvoidAlliances] = useState('');
  const [loading, setLoading] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [baseSystemCost, setBaseSystemCost] = useState(DEFAULT_WEIGHTS.base_system_cost);
  const [distanceExponent, setDistanceExponent] = useState(DEFAULT_WEIGHTS.distance_exponent);
  const [dangerWeight, setDangerWeight] = useState(DEFAULT_WEIGHTS.danger_weight);
  const [jumpsWeight, setJumpsWeight] = useState(DEFAULT_WEIGHTS.jumps_weight);
  const [deadEndBonus, setDeadEndBonus] = useState(DEFAULT_WEIGHTS.dead_end_bonus);
  const [posMoonBonus, setPosMoonBonus] = useState(DEFAULT_WEIGHTS.pos_moon_bonus);

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

    const params = {
      origin_id: originId,
      destination_id: destId,
      ship_class: shipClass,
      jdc_level: jdc,
      jfc_level: jfc,
      initial_fatigue: fatigue,
      mode,
      avoid_alliances: avoidAlliances,
      base_system_cost: baseSystemCost,
      distance_exponent: distanceExponent,
      danger_weight: dangerWeight,
      jumps_weight: jumpsWeight,
      dead_end_bonus: deadEndBonus,
      pos_moon_bonus: posMoonBonus,
    };

    esRef.current = planRouteSSE(
      params,
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
              jf_skill: jfSkill,
              initial_fatigue: fatigue,
              mode,
              base_system_cost: baseSystemCost,
              distance_exponent: distanceExponent,
              danger_weight: dangerWeight,
              jumps_weight: jumpsWeight,
              dead_end_bonus: deadEndBonus,
              pos_moon_bonus: posMoonBonus,
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

  function resetWeights() {
    setBaseSystemCost(DEFAULT_WEIGHTS.base_system_cost);
    setDistanceExponent(DEFAULT_WEIGHTS.distance_exponent);
    setDangerWeight(DEFAULT_WEIGHTS.danger_weight);
    setJumpsWeight(DEFAULT_WEIGHTS.jumps_weight);
    setDeadEndBonus(DEFAULT_WEIGHTS.dead_end_bonus);
    setPosMoonBonus(DEFAULT_WEIGHTS.pos_moon_bonus);
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
      <div className={`grid grid-cols-2 gap-3 items-end ${shipClass === 'Jump Freighter' ? 'md:grid-cols-[2fr_1fr_1fr_1fr_2fr_1fr_auto]' : 'md:grid-cols-[2fr_1fr_1fr_2fr_1fr_auto]'}`}>
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
          <label className="block text-sm mb-1 text-gray-300">JDC</label>
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
          <label className="block text-sm mb-1 text-gray-300">JFC</label>
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
        {shipClass === 'Jump Freighter' && (
          <div>
            <label className="block text-sm mb-1 text-gray-300">JF</label>
            <select
              value={jfSkill}
              onChange={(e) => setJfSkill(Number(e.target.value))}
              className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-gray-200"
            >
              {[0, 1, 2, 3, 4, 5].map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>
        )}
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

      {mode !== 'direct' && (
        <div className="mt-3">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-sm text-gray-400 hover:text-gray-200 flex items-center gap-1"
          >
            <span>{showAdvanced ? '▼' : '▶'}</span>
            Advanced Weights
          </button>

          {showAdvanced && (
            <div className="mt-2 p-3 bg-gray-900/50 rounded border border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">
                  Adjust how the routing algorithm scores each system
                </span>
                <button
                  onClick={resetWeights}
                  className="text-xs text-gray-500 hover:text-gray-300 underline"
                >
                  Reset defaults
                </button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs mb-1 text-gray-400">
                    Base System Cost
                    <span className="block text-gray-600">Baseline per system</span>
                  </label>
                  <input
                    type="number"
                    value={baseSystemCost}
                    onChange={(e) => setBaseSystemCost(Number(e.target.value))}
                    min={0}
                    className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-600 text-gray-200 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs mb-1 text-gray-400">
                    Distance Exponent
                    <span className="block text-gray-600">1.0 = linear, 2.0 = heavy</span>
                  </label>
                  <input
                    type="number"
                    value={distanceExponent}
                    onChange={(e) => setDistanceExponent(Number(e.target.value))}
                    min={1}
                    max={3}
                    step={0.1}
                    className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-600 text-gray-200 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs mb-1 text-gray-400">
                    Danger Weight
                    <span className="block text-gray-600">Cost per kill</span>
                  </label>
                  <input
                    type="number"
                    value={dangerWeight}
                    onChange={(e) => setDangerWeight(Number(e.target.value))}
                    min={0}
                    className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-600 text-gray-200 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs mb-1 text-gray-400">
                    Jumps Weight
                    <span className="block text-gray-600">Cost per jump</span>
                  </label>
                  <input
                    type="number"
                    value={jumpsWeight}
                    onChange={(e) => setJumpsWeight(Number(e.target.value))}
                    min={0}
                    className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-600 text-gray-200 text-sm"
                  />
                </div>
                {mode === 'safe' && (
                  <div>
                    <label className="block text-xs mb-1 text-gray-400">
                      Dead End Bonus
                      <span className="block text-gray-600">Bonus for 1-gate systems</span>
                    </label>
                    <input
                      type="number"
                      value={deadEndBonus}
                      onChange={(e) => setDeadEndBonus(Number(e.target.value))}
                      min={0}
                      className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-600 text-gray-200 text-sm"
                    />
                  </div>
                )}
                {mode === 'pos' && (
                  <div>
                    <label className="block text-xs mb-1 text-gray-400">
                      Moon Bonus
                      <span className="block text-gray-600">Bonus per moon</span>
                    </label>
                    <input
                      type="number"
                      value={posMoonBonus}
                      onChange={(e) => setPosMoonBonus(Number(e.target.value))}
                      min={0}
                      className="w-full px-2 py-1.5 rounded bg-gray-800 border border-gray-600 text-gray-200 text-sm"
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
