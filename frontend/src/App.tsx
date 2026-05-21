import { useState, useRef } from 'react';
import RouteControls from './components/RouteControls';
import type { RouteParams } from './components/RouteControls';
import RouteTable from './components/RouteTable';
import MapView from './components/MapView';
import type { RouteResult } from './types';
import { formatTime } from './utils/format';
import { swapHop } from './api';

export default function App() {
  const [result, setResult] = useState<RouteResult | null>(null);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState('');
  // Tracks the system to pan/focus the map on (set when the user picks an
  // origin or destination from the autocomplete).
  const [focusSystemId, setFocusSystemId] = useState<number | null>(null);
  const routeParamsRef = useRef<RouteParams | null>(null);

  function handleResult(r: RouteResult, params?: RouteParams) {
    setError('');
    setProgress('');
    setResult(r);
    if (params) routeParamsRef.current = params;
  }

  function handleError(msg: string) {
    setError(msg);
    setProgress('');
    setResult(null);
  }

  function handleProgress(msg: string) {
    setError('');
    setProgress(msg);
  }

  async function handleSwap(hopIndex: number, altSystemId: number) {
    if (!result || !routeParamsRef.current) return;
    const path = result.steps.map((s) => s.system_id);
    setProgress('Swapping system...');
    try {
      const swapped = await swapHop({
        path,
        hop: hopIndex,
        alt_id: altSystemId,
        ...routeParamsRef.current,
      });
      if (swapped.error) {
        setError(swapped.error);
        setProgress('');
      } else {
        handleResult(swapped);
      }
    } catch (e) {
      setError('Swap failed: ' + (e as Error).message);
      setProgress('');
    }
  }

  // Multi-label search picks waits implicitly, so we always show its
  // primary result — there's no separate "optimized" alternative now.
  const activeSteps = result ? result.steps : [];
  const activeWait = result ? result.total_wait_minutes : 0;
  const activeFuel = result ? result.total_fuel : 0;
  const totalLy = activeSteps.reduce(
    (acc, s) => acc + (s.edge_type === 'jump' ? s.distance_ly : 0),
    0,
  );
  const arrivalHHMM = (() => {
    if (!result || activeWait <= 0) return null;
    const ms = Date.now() + activeWait * 60_000;
    return new Date(ms).toISOString().slice(11, 16);
  })();

  function copyAsText() {
    if (!result) return;
    const lines = activeSteps.map((s, i) =>
      i === 0
        ? `${s.system_name} (${s.security.toFixed(1)}) ${s.sov_owner ? `[${s.sov_owner}]` : ''}`
        : `→ ${s.system_name} (${s.security.toFixed(1)}) ${s.distance_ly} LY | Wait: ${formatTime(s.wait_minutes)} | Fatigue: ${formatTime(s.fatigue_after_minutes)} ${s.sov_owner ? `[${s.sov_owner}]` : ''}`,
    );
    const jdN = result.total_jumps || 0;
    const gateN = result.total_gate_hops || 0;
    const totalN = jdN + gateN;
    const breakdown = gateN > 0 ? ` (${jdN} JD + ${gateN} gate)` : '';
    lines.push(`\nTotal: ${totalN} hops${breakdown}, ${activeFuel.toLocaleString()} fuel, ${formatTime(activeWait)} wait`);
    if (result.quiet_hours) {
      lines.push(`Quietest: ${String(result.quiet_hours.start).padStart(2, '0')}:00-${String(result.quiet_hours.end).padStart(2, '0')}:00 UTC`);
    }
    navigator.clipboard.writeText(lines.join('\n'));
  }

  function openInDotlan() {
    const shipClass = routeParamsRef.current?.ship_class ?? '';
    const dotlanShipMap: Record<string, string> = {
      'Carrier/Dreadnought/FAX': 'Archon',
      'Supercarrier/Titan': 'Ragnarok',
      Rorqual: 'Rorqual',
      'Black Ops': 'Sin',
      'Jump Freighter': 'Rhea',
    };
    const dotlanShip = dotlanShipMap[shipClass] ?? 'Archon';
    const jdc = routeParamsRef.current?.jdc_level ?? 5;
    const jfc = routeParamsRef.current?.jfc_level ?? 4;
    const jfSkill = routeParamsRef.current?.jf_skill ?? 0;
    const systems = activeSteps.map((s) => s.system_name).join(':');
    const url = `https://evemaps.dotlan.net/jump/${dotlanShip},${jdc}${jfc}${jfSkill}/${systems}`;
    window.open(url, '_blank');
  }

  return (
    <>
      <header className="bg-[var(--color-paper)] border-b border-[var(--color-line)]">
        <div className="max-w-[1080px] mx-auto px-[22px] py-[14px] flex items-baseline gap-5">
          <h1 className="m-0 text-[18px] font-semibold tracking-tight">
            <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-accent)] mr-2 align-middle translate-y-[-1px]" />
            EVE CapNav
          </h1>
          <span className="text-[var(--color-muted)] text-xs">
            Capital jump routing for null &amp; lowsec
          </span>
        </div>
      </header>

      <div className="max-w-[1080px] mx-auto px-[22px] py-5 pb-10">
        <RouteControls
          onResult={handleResult}
          onError={handleError}
          onProgress={handleProgress}
          onSystemFocus={setFocusSystemId}
        />

        {progress && (
          <div className="card mb-[18px] px-4 py-2 flex items-center gap-2 text-[var(--color-accent)]">
            <span className="inline-block w-3.5 h-3.5 border-2 border-[var(--color-accent)] border-t-transparent rounded-full animate-spin" />
            <span className="text-[13px]">{progress}</span>
          </div>
        )}

        {error && (
          <div className="mb-[18px] px-4 py-2 rounded-lg border border-[rgba(248,81,73,0.4)] bg-[rgba(248,81,73,0.10)] text-[var(--color-bad)] text-[13px]">
            {error}
          </div>
        )}

        {result && result.steps.length > 0 && (
          <div className="grid grid-cols-[repeat(6,1fr)_auto] bg-[var(--color-paper)] border border-[var(--color-line)] rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.35)] overflow-hidden mb-[18px]">
            <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
              <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                Total Hops
              </div>
              <div className="text-[18px] font-semibold">
                {(result.total_jumps || 0) + (result.total_gate_hops || 0)}
              </div>
              <div className="text-xs text-[var(--color-muted)]">
                {result.total_jumps || 0} JD
                {result.total_gate_hops ? ` + ${result.total_gate_hops} gate` : ''}
              </div>
            </div>
            <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
              <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                Total LY
              </div>
              <div className="text-[18px] font-semibold">{totalLy.toFixed(1)}</div>
              <div className="text-xs text-[var(--color-muted)]">jump-drive distance</div>
            </div>
            <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
              <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                Fuel
              </div>
              <div className="text-[18px] font-semibold">
                {activeFuel.toLocaleString()}
              </div>
              <div className="text-xs text-[var(--color-muted)]">
                {result.total_fuel_isk && result.total_fuel_isk > 0 ? (
                  <span data-testid="fuel-isk">
                    ~{(result.total_fuel_isk / 1_000_000).toFixed(1)}M ISK
                  </span>
                ) : (
                  'isotopes'
                )}
              </div>
            </div>
            <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
              <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                Total Wait
              </div>
              <div className="text-[18px] font-semibold">{formatTime(activeWait)}</div>
              <div className="text-xs text-[var(--color-muted)]">
                {arrivalHHMM ? (
                  <span data-testid="arrival-time">arrive ~{arrivalHHMM} UTC</span>
                ) : (
                  'red + blue timers'
                )}
              </div>
            </div>
            <div
              className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]"
              title={
                result.risk_breakdown
                  ? `${result.risk_breakdown.kills} kills · ${result.risk_breakdown.peak_jumps} peak jumps · ${result.risk_breakdown.dead_ends} dead-ends · ${result.risk_breakdown.hostile_systems} hostile`
                  : undefined
              }
            >
              <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                Risk
              </div>
              {(() => {
                const r = result.risk_score ?? 0;
                const color =
                  r >= 60
                    ? 'var(--color-bad)'
                    : r >= 30
                    ? 'var(--color-warn)'
                    : 'var(--color-good)';
                return (
                  <div
                    className="text-[18px] font-semibold"
                    style={{ color }}
                    data-testid="risk-score"
                    data-risk-band={r >= 60 ? 'high' : r >= 30 ? 'mid' : 'low'}
                  >
                    {r}%
                  </div>
                );
              })()}
              <div className="text-xs text-[var(--color-muted)]">composite</div>
            </div>
            <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
              <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                Quietest
              </div>
              <div
                className="text-[14px] font-semibold text-[var(--color-good)] leading-tight"
                data-testid="quiet-jumps-line"
              >
                {result.quiet_jumps
                  ? `${String(result.quiet_jumps.start).padStart(2, '0')}–${String(result.quiet_jumps.end).padStart(2, '0')}`
                  : '—'}
                <span className="text-[10.5px] text-[var(--color-muted)] font-normal ml-1.5">
                  jumps
                </span>
              </div>
              <div
                className="text-[14px] font-semibold text-[var(--color-bad)] leading-tight mt-0.5"
                data-testid="quiet-kills-line"
              >
                {result.quiet_hours
                  ? `${String(result.quiet_hours.start).padStart(2, '0')}–${String(result.quiet_hours.end).padStart(2, '0')}`
                  : '—'}
                <span className="text-[10.5px] text-[var(--color-muted)] font-normal ml-1.5">
                  kills
                </span>
              </div>
            </div>
            <div className="px-[18px] py-[14px] flex flex-col gap-1.5 items-end justify-center">
              <button
                onClick={copyAsText}
                className="text-[13px] text-[var(--color-accent)] hover:underline"
              >
                Copy as text
              </button>
              <button
                onClick={openInDotlan}
                className="text-[13px] text-[var(--color-accent)] hover:underline"
              >
                Open in Dotlan
              </button>
            </div>
          </div>
        )}

        {result && result.steps.length > 0 && (
          <section className="card">
            <RouteTable
              steps={activeSteps}
              zkill={result.zkill}
              alternatives={result.alternatives}
              mode={routeParamsRef.current?.mode as 'safe' | 'direct' | 'pos' | undefined}
              onSwap={handleSwap}
            />
          </section>
        )}

        <div className="mt-[18px]">
          <MapView
            route={activeSteps.length > 0 ? activeSteps : undefined}
            focusSystemId={focusSystemId}
          />
        </div>
      </div>
    </>
  );
}
