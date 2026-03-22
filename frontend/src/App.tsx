import { useState, useRef } from 'react';
import RouteControls from './components/RouteControls';
import RouteTable from './components/RouteTable';
import type { RouteResult } from './types';
import { formatTime } from './utils/format';
import { swapHop } from './api';

export default function App() {
  const [result, setResult] = useState<RouteResult | null>(null);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState('');
  const routeParamsRef = useRef<{
    ship_class: string;
    jdc_level: number;
    jfc_level: number;
    initial_fatigue: number;
    mode: string;
  } | null>(null);
  const [showOptimized, setShowOptimized] = useState(false);

  function handleResult(r: RouteResult, params?: { ship_class: string; jdc_level: number; jfc_level: number; initial_fatigue: number; mode: string }) {
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

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-semibold text-center mb-4">
        EVE CapNav{' '}
        <span className="text-gray-500 text-lg">Capital Ship Route Planner</span>
      </h1>

      <RouteControls
        onResult={handleResult}
        onError={handleError}
        onProgress={handleProgress}
      />

      {progress && (
        <div className="bg-blue-900/30 border border-blue-700 text-blue-300 px-4 py-2 rounded mb-4 flex items-center gap-2">
          <span className="inline-block w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          {progress}
        </div>
      )}

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 px-4 py-2 rounded mb-4">
          {error}
        </div>
      )}

      {result && result.steps.length > 0 && (
        <>
          {result.optimized && (
            <div className="flex gap-2 mb-3">
              <button
                onClick={() => setShowOptimized(false)}
                className={`px-3 py-1.5 rounded text-sm font-medium ${
                  !showOptimized
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                Minimum Wait
              </button>
              <button
                onClick={() => setShowOptimized(true)}
                className={`px-3 py-1.5 rounded text-sm font-medium ${
                  showOptimized
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                Optimized (+{formatTime(result.optimized.extra_wait_minutes)}/hop)
              </button>
              {showOptimized && result.optimized.total_wait_minutes < result.total_wait_minutes && (
                <span className="text-green-400 text-sm self-center">
                  Saves {formatTime(result.total_wait_minutes - result.optimized.total_wait_minutes)}
                </span>
              )}
            </div>
          )}
          <div className="text-lg mb-3">
            <strong>{result.total_jumps} jumps</strong> ·{' '}
            <strong>{activeFuel.toLocaleString()}</strong> fuel ·{' '}
            <strong>{formatTime(activeWait)}</strong> total wait
            {result.quiet_hours && (
              <span className="ml-3 text-sm text-blue-400">
                Quietest window: {String(result.quiet_hours.start).padStart(2, '0')}:00 – {String(result.quiet_hours.end).padStart(2, '0')}:00 UTC
              </span>
            )}
          </div>
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => {
                const lines = activeSteps.map((s, i) =>
                  i === 0
                    ? `${s.system_name} (${s.security.toFixed(1)}) ${s.sov_owner ? `[${s.sov_owner}]` : ''}`
                    : `→ ${s.system_name} (${s.security.toFixed(1)}) ${s.distance_ly} LY | Wait: ${formatTime(s.wait_minutes)} | Fatigue: ${formatTime(s.fatigue_after_minutes)} ${s.sov_owner ? `[${s.sov_owner}]` : ''}`
                );
                lines.push(`\nTotal: ${result.total_jumps} jumps, ${activeFuel.toLocaleString()} fuel, ${formatTime(activeWait)} wait`);
                if (result.quiet_hours) {
                  lines.push(`Quietest: ${String(result.quiet_hours.start).padStart(2, '0')}:00-${String(result.quiet_hours.end).padStart(2, '0')}:00 UTC`);
                }
                navigator.clipboard.writeText(lines.join('\n'));
              }}
              className="px-3 py-1 rounded text-sm bg-gray-700 text-gray-300 hover:bg-gray-600"
            >
              Copy as Text
            </button>
          </div>
          <RouteTable steps={activeSteps} zkill={result.zkill} alternatives={result.alternatives} onSwap={handleSwap} />
        </>
      )}
    </div>
  );
}
