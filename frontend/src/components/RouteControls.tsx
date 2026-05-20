import { useState, useEffect, useRef } from 'react';
import SystemSearch from './SystemSearch';
import { getShipClasses, planRouteSSE } from '../api';
import type { ShipClass, RouteResult } from '../types';

const DEFAULT_WEIGHTS = {
  base_system_cost: 200,
  distance_exponent: 1.5,
  danger_weight: 600,
  jumps_weight: 60,
  activity_weight: 30,
  dead_end_penalty: 100,
  pos_moon_bonus: 5,
  wait_weight: 0.2,
};

// Slider mapping: 0 (Quickest) → wait_weight 0.05; 100 (Least Jumps) → 20.
// Linear scale; default 0.2 lands near the "Quickest" end which mirrors the
// pre-multi-label behavior (small fatigue penalty).
const WAIT_WEIGHT_MIN = 0.05;
const WAIT_WEIGHT_MAX = 20;
const sliderToWaitWeight = (s: number): number =>
  WAIT_WEIGHT_MIN + (s / 100) * (WAIT_WEIGHT_MAX - WAIT_WEIGHT_MIN);
const waitWeightToSlider = (w: number): number => {
  const raw = ((w - WAIT_WEIGHT_MIN) / (WAIT_WEIGHT_MAX - WAIT_WEIGHT_MIN)) * 100;
  return Math.max(0, Math.min(100, raw));
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
  activity_weight: number;
  dead_end_penalty: number;
  pos_moon_bonus: number;
  wait_weight: number;
}

interface Props {
  onResult: (result: RouteResult, params: RouteParams) => void;
  onError: (msg: string) => void;
  onProgress: (msg: string) => void;
  /** Fires whenever the user picks an origin or destination from the
   *  autocomplete, so the parent can pan/focus the map there. */
  onSystemFocus?: (id: number) => void;
}

export default function RouteControls({ onResult, onError, onProgress, onSystemFocus }: Props) {
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

  const [gateMode, setGateMode] = useState<'off' | 'interregional' | 'all'>('off');
  const [gateEquivalentJumps, setGateEquivalentJumps] = useState(5);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [baseSystemCost, setBaseSystemCost] = useState(DEFAULT_WEIGHTS.base_system_cost);
  const [distanceExponent, setDistanceExponent] = useState(DEFAULT_WEIGHTS.distance_exponent);
  const [dangerWeight, setDangerWeight] = useState(DEFAULT_WEIGHTS.danger_weight);
  const [jumpsWeight, setJumpsWeight] = useState(DEFAULT_WEIGHTS.jumps_weight);
  const [activityWeight, setActivityWeight] = useState(DEFAULT_WEIGHTS.activity_weight);
  const [deadEndPenalty, setDeadEndPenalty] = useState(DEFAULT_WEIGHTS.dead_end_penalty);
  const [posMoonBonus, setPosMoonBonus] = useState(DEFAULT_WEIGHTS.pos_moon_bonus);
  const [waitWeight, setWaitWeight] = useState(DEFAULT_WEIGHTS.wait_weight);

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
      gate_mode: gateMode,
      gate_equivalent_jumps: gateEquivalentJumps,
      base_system_cost: baseSystemCost,
      distance_exponent: distanceExponent,
      danger_weight: dangerWeight,
      jumps_weight: jumpsWeight,
      activity_weight: activityWeight,
      dead_end_penalty: deadEndPenalty,
      pos_moon_bonus: posMoonBonus,
      wait_weight: waitWeight,
    };

    esRef.current = planRouteSSE(
      params,
      {
        onProgress: (msg) => onProgress(msg),
        onResult: (result) => {
          setLoading(false);
          if (result.error && !result.steps?.length) {
            const isNoRoute = /no route/i.test(result.error);
            if (isNoRoute && gateMode === 'off') {
              onError(
                'No route found at this ship’s jump range. Try enabling stargate hops, or use a longer-range ship class.',
              );
            } else if (isNoRoute && gateMode === 'interregional') {
              onError(
                'No route found. Try "All null/low gates" mode, or check that the SDE has stargate data (backend log: "Gate graph: 0 directed edges" means the SDE is missing).',
              );
            } else if (isNoRoute) {
              onError(
                'No route found. Origin and destination may not be connected via stargates — verify both are in null/low sec.',
              );
            } else {
              onError(result.error);
            }
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
              activity_weight: activityWeight,
              dead_end_penalty: deadEndPenalty,
              pos_moon_bonus: posMoonBonus,
              wait_weight: waitWeight,
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
    setActivityWeight(DEFAULT_WEIGHTS.activity_weight);
    setDeadEndPenalty(DEFAULT_WEIGHTS.dead_end_penalty);
    setPosMoonBonus(DEFAULT_WEIGHTS.pos_moon_bonus);
    setWaitWeight(DEFAULT_WEIGHTS.wait_weight);
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
            <SystemSearch
              label="Origin"
              onSelect={(id) => {
                setOriginId(id);
                onSystemFocus?.(id);
              }}
            />
          </div>
          <div className="flex flex-col">
            <SystemSearch
              label="Destination"
              onSelect={(id) => {
                setDestId(id);
                onSystemFocus?.(id);
              }}
            />
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
          <div className="flex flex-col">
            <label className="field-label">Stargate hops</label>
            <select
              value={gateMode}
              onChange={(e) =>
                setGateMode(e.target.value as 'off' | 'interregional' | 'all')
              }
              className="select"
            >
              <option value="off">Off (jumps only)</option>
              <option value="interregional">Inter-regional gates as shortcuts</option>
              <option value="all">All null/low gates</option>
            </select>
          </div>
          {gateMode !== 'off' && (
            <div className="flex flex-col">
              <label className="field-label">Gate cost (= N jumps)</label>
              <input
                type="number"
                value={gateEquivalentJumps}
                onChange={(e) => setGateEquivalentJumps(Number(e.target.value))}
                min={0}
                step={0.5}
                className="input"
              />
              <span className="text-[11px] text-[var(--color-muted)] mt-[3px]">
                Take gate when it saves ≥ this many jumps.
              </span>
            </div>
          )}
        </div>

        <div className="mt-4 pt-[14px] border-t border-[var(--color-line-soft)]">
          <div className="flex items-center justify-between mb-1">
            <label className="field-label !mb-0">Route preference</label>
            <span className="text-[11px] text-[var(--color-muted)]">
              wait_weight = {waitWeight.toFixed(2)}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={waitWeightToSlider(waitWeight)}
            onChange={(e) =>
              setWaitWeight(sliderToWaitWeight(Number(e.target.value)))
            }
            className="w-full"
          />
          <div className="flex justify-between text-[11px] text-[var(--color-muted)] mt-[3px]">
            <span>Least jumps (tolerate fatigue, fewer JD hops)</span>
            <span>Quickest (avoid fatigue waits, more hops OK)</span>
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
            <label className="flex justify-between items-center gap-2">
              <span>Activity weight</span>
              <input
                type="number"
                value={activityWeight}
                onChange={(e) => setActivityWeight(Number(e.target.value))}
                min={0}
                className="input w-[80px] py-1 px-2 text-[12px]"
              />
            </label>
            <label className="flex justify-between items-center gap-2">
              <span>Wait weight (override)</span>
              <input
                type="number"
                value={waitWeight}
                onChange={(e) => setWaitWeight(Number(e.target.value))}
                min={0}
                step={0.05}
                className="input w-[80px] py-1 px-2 text-[12px]"
              />
            </label>
            {mode === 'safe' && (
              <label className="flex justify-between items-center gap-2">
                <span>Dead-end penalty</span>
                <input
                  type="number"
                  value={deadEndPenalty}
                  onChange={(e) => setDeadEndPenalty(Number(e.target.value))}
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
