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

  const isJf = shipClass === 'Jump Freighter';

  return (
    <section className="card mb-[18px]">
      <div className="card-head">
        <h2>Route parameters</h2>
        <span className="help">Enter origin, destination, and your skills.</span>
      </div>
      <div className="card-body">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-x-[18px] gap-y-[14px]">
          <div className="flex flex-col">
            <SystemSearch label="Origin" onSelect={(id) => setOriginId(id)} />
          </div>
          <div className="flex flex-col">
            <SystemSearch label="Destination" onSelect={(id) => setDestId(id)} />
          </div>
          <div className="flex flex-col">
            <label className="field-label">Ship class</label>
            <select
              value={shipClass}
              onChange={(e) => setShipClass(e.target.value)}
              className="select"
            >
              {shipClasses.map((c) => (
                <option key={c.label} value={c.label}>
                  {c.label} ({c.base_range_ly} LY)
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col">
            <label className="field-label">Routing mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'safe' | 'direct' | 'pos')}
              className="select"
            >
              <option value="safe">Safe (avoid danger)</option>
              <option value="direct">Direct (shortest path)</option>
              <option value="pos">POS Hopping (prefer moons)</option>
            </select>
          </div>

          <div className="flex flex-col">
            <label className="field-label">JDC level</label>
            <select
              value={jdc}
              onChange={(e) => setJdc(Number(e.target.value))}
              className="select"
            >
              {[0, 1, 2, 3, 4, 5].map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col">
            <label className="field-label">JFC level</label>
            <select
              value={jfc}
              onChange={(e) => setJfc(Number(e.target.value))}
              className="select"
            >
              {[0, 1, 2, 3, 4, 5].map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>
          {isJf && (
            <div className="flex flex-col">
              <label className="field-label">JF skill</label>
              <select
                value={jfSkill}
                onChange={(e) => setJfSkill(Number(e.target.value))}
                className="select"
              >
                {[0, 1, 2, 3, 4, 5].map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="flex flex-col">
            <label className="field-label">Initial fatigue (min)</label>
            <input
              type="number"
              value={fatigue}
              onChange={(e) => setFatigue(Number(e.target.value))}
              min={0}
              max={720}
              className="input"
            />
            <span className="text-[11px] text-[var(--color-muted)] mt-[3px]">
              Leave 0 if rested.
            </span>
          </div>
          <div className={`flex flex-col ${isJf ? 'md:col-span-3' : 'md:col-span-2'}`}>
            <label className="field-label">Avoid alliances</label>
            <input
              type="text"
              value={avoidAlliances}
              onChange={(e) => setAvoidAlliances(e.target.value)}
              placeholder="Goonswarm Federation, Pandemic Horde, ..."
              className="input"
            />
          </div>
        </div>

        <div className="mt-4 pt-[14px] border-t border-[var(--color-line-soft)] flex items-center gap-3">
          {mode !== 'direct' && (
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-[12px] text-[var(--color-accent)] hover:underline list-none cursor-pointer"
            >
              {showAdvanced ? '▾' : '▸'} Advanced cost weights
            </button>
          )}
          <div className="flex-1" />
          {mode !== 'direct' && showAdvanced && (
            <button
              type="button"
              onClick={resetWeights}
              className="text-[12px] text-[var(--color-muted)] hover:text-[var(--color-ink)] underline"
            >
              Reset defaults
            </button>
          )}
          <button onClick={handlePlan} disabled={loading} className="btn-primary">
            {loading ? 'Planning…' : 'Plan Route'}
          </button>
        </div>

        {mode !== 'direct' && showAdvanced && (
          <div className="mt-3 pt-3 border-t border-dashed border-[var(--color-line)] grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-2.5 text-[12px]">
            <label className="flex justify-between items-center gap-2">
              <span>Base system cost</span>
              <input
                type="number"
                value={baseSystemCost}
                onChange={(e) => setBaseSystemCost(Number(e.target.value))}
                min={0}
                className="input w-[80px] py-1 px-2 text-[12px]"
              />
            </label>
            <label className="flex justify-between items-center gap-2">
              <span>Distance exponent</span>
              <input
                type="number"
                value={distanceExponent}
                onChange={(e) => setDistanceExponent(Number(e.target.value))}
                min={1}
                max={3}
                step={0.1}
                className="input w-[80px] py-1 px-2 text-[12px]"
              />
            </label>
            <label className="flex justify-between items-center gap-2">
              <span>Danger weight</span>
              <input
                type="number"
                value={dangerWeight}
                onChange={(e) => setDangerWeight(Number(e.target.value))}
                min={0}
                className="input w-[80px] py-1 px-2 text-[12px]"
              />
            </label>
            <label className="flex justify-between items-center gap-2">
              <span>Jumps weight</span>
              <input
                type="number"
                value={jumpsWeight}
                onChange={(e) => setJumpsWeight(Number(e.target.value))}
                min={0}
                className="input w-[80px] py-1 px-2 text-[12px]"
              />
            </label>
            {mode === 'safe' && (
              <label className="flex justify-between items-center gap-2">
                <span>Dead-end bonus</span>
                <input
                  type="number"
                  value={deadEndBonus}
                  onChange={(e) => setDeadEndBonus(Number(e.target.value))}
                  min={0}
                  className="input w-[80px] py-1 px-2 text-[12px]"
                />
              </label>
            )}
            {mode === 'pos' && (
              <label className="flex justify-between items-center gap-2">
                <span>Moon bonus</span>
                <input
                  type="number"
                  value={posMoonBonus}
                  onChange={(e) => setPosMoonBonus(Number(e.target.value))}
                  min={0}
                  className="input w-[80px] py-1 px-2 text-[12px]"
                />
              </label>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
