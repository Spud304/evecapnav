import { useState, useRef } from 'react';
import RouteControls from './components/RouteControls';
import type { RouteParams } from './components/RouteControls';
import RouteTable from './components/RouteTable';
import type { RouteResult } from './types';
import { formatTime } from './utils/format';
import { swapHop } from './api';

export default function App() {
  const [result, setResult] = useState<RouteResult | null>(null);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState('');
  const routeParamsRef = useRef<RouteParams | null>(null);
  const [showOptimized, setShowOptimized] = useState(false);

  function handleResult(r: RouteResult, params?: RouteParams) {
    setError('');
    setProgress('');
    setResult(r);
    setShowOptimized(false);
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

  const activeSteps = result
    ? showOptimized && result.optimized
      ? result.optimized.steps
      : result.steps
    : [];

  const activeWait = result
    ? showOptimized && result.optimized
      ? result.optimized.total_wait_minutes
      : result.total_wait_minutes
    : 0;

  const activeFuel = result
    ? showOptimized && result.optimized
      ? result.optimized.total_fuel
      : result.total_fuel
    : 0;

  function copyAsText() {
    if (!result) return;
    const lines = activeSteps.map((s, i) =>
      i === 0
        ? `${s.system_name} (${s.security.toFixed(1)}) ${s.sov_owner ? `[${s.sov_owner}]` : ''}`
        : `→ ${s.system_name} (${s.security.toFixed(1)}) ${s.distance_ly} LY | Wait: ${formatTime(s.wait_minutes)} | Fatigue: ${formatTime(s.fatigue_after_minutes)} ${s.sov_owner ? `[${s.sov_owner}]` : ''}`,
    );
    lines.push(`\nTotal: ${result.total_jumps} jumps, ${activeFuel.toLocaleString()} fuel, ${formatTime(activeWait)} wait`);
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
      <header className="bg-white border-b border-[var(--color-line)]">
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
        />

        {progress && (
          <div className="card mb-[18px] px-4 py-2 flex items-center gap-2 text-[var(--color-accent)]">
            <span className="inline-block w-3.5 h-3.5 border-2 border-[var(--color-accent)] border-t-transparent rounded-full animate-spin" />
            <span className="text-[13px]">{progress}</span>
          </div>
        )}

        {error && (
          <div className="mb-[18px] px-4 py-2 rounded-lg border border-red-300 bg-red-50 text-red-800 text-[13px]">
            {error}
          </div>
        )}

        {result && result.steps.length > 0 && (
          <>
            <div className="grid grid-cols-[repeat(4,1fr)_auto] bg-white border border-[var(--color-line)] rounded-lg shadow-[0_1px_1px_rgba(20,25,40,0.04)] overflow-hidden mb-[18px]">
              <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
                <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                  Total Jumps
                </div>
                <div className="text-[18px] font-semibold">{result.total_jumps}</div>
                <div className="text-xs text-[var(--color-muted)]">
                  avg{' '}
                  {result.total_jumps > 0
                    ? (
                        activeSteps.reduce((s, x) => s + x.distance_ly, 0) /
                        result.total_jumps
                      ).toFixed(2)
                    : '—'}{' '}
                  LY
                </div>
              </div>
              <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
                <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                  Fuel
                </div>
                <div className="text-[18px] font-semibold">
                  {activeFuel.toLocaleString()}
                </div>
                <div className="text-xs text-[var(--color-muted)]">isotopes</div>
              </div>
              <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
                <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                  Total Wait
                </div>
                <div className="text-[18px] font-semibold">{formatTime(activeWait)}</div>
                <div className="text-xs text-[var(--color-muted)]">red + blue timers</div>
              </div>
              <div className="px-[18px] py-[14px] border-r border-[var(--color-line-soft)]">
                <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-1">
                  Quietest Window
                </div>
                <div className="text-[18px] font-semibold">
                  {result.quiet_hours
                    ? `${String(result.quiet_hours.start).padStart(2, '0')}–${String(result.quiet_hours.end).padStart(2, '0')}`
                    : '—'}
                </div>
                <div className="text-xs text-[var(--color-muted)]">UTC</div>
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

            <section className="card">
              {result.optimized && (
                <div className="flex gap-1 pt-[10px] px-[18px] border-b border-[var(--color-line-soft)]">
                  <button
                    onClick={() => setShowOptimized(false)}
                    className={
                      !showOptimized
                        ? 'bg-white border border-[var(--color-line)] border-b-0 text-[var(--color-ink)] font-semibold relative top-px rounded-t-md px-3.5 py-[7px] text-[12px] cursor-pointer'
                        : 'bg-transparent border border-transparent text-[var(--color-muted)] rounded-t-md px-3.5 py-[7px] text-[12px] cursor-pointer'
                    }
                  >
                    Minimum Wait
                  </button>
                  <button
                    onClick={() => setShowOptimized(true)}
                    className={
                      showOptimized
                        ? 'bg-white border border-[var(--color-line)] border-b-0 text-[var(--color-ink)] font-semibold relative top-px rounded-t-md px-3.5 py-[7px] text-[12px] cursor-pointer'
                        : 'bg-transparent border border-transparent text-[var(--color-muted)] rounded-t-md px-3.5 py-[7px] text-[12px] cursor-pointer'
                    }
                  >
                    Optimized (+{formatTime(result.optimized.extra_wait_minutes)}/hop)
                  </button>
                  {showOptimized &&
                    result.optimized.total_wait_minutes < result.total_wait_minutes && (
                      <span className="self-center ml-2 text-[11px] text-[var(--color-good)]">
                        Saves{' '}
                        {formatTime(
                          result.total_wait_minutes - result.optimized.total_wait_minutes,
                        )}
                      </span>
                    )}
                </div>
              )}
              <RouteTable
                steps={activeSteps}
                zkill={result.zkill}
                alternatives={result.alternatives}
                jumpDataWindow={result.jump_data_window}
                onSwap={handleSwap}
              />
            </section>
          </>
        )}
      </div>
    </>
  );
}
