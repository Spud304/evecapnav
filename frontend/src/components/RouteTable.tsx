import React, { useState } from 'react';
import type { RouteStep, ZkillSystemStats, AlternativeSystem } from '../types';
import { formatTime, secBand, secColor } from '../utils/format';
import { getSovColor } from '../utils/sovColors';
import ThreatModal from './ThreatModal';
import Sparkline from './Sparkline';

interface Props {
  steps: RouteStep[];
  zkill?: Record<number, ZkillSystemStats>;
  alternatives?: Record<string, AlternativeSystem[]>;
  /** Routing mode — drives whether the Moons column is shown. */
  mode?: 'safe' | 'direct' | 'pos';
  onSwap?: (hopIndex: number, altSystemId: number) => void;
}

/** Pill background + text for the sec-band marker.
 *
 * HS gets a hard-red warning (capital ships can't gate-jump into HS, so any
 * HS step on a cap route is almost always a bug or a mis-set parameter).
 */
function secBandStyle(band: 'HS' | 'LS' | 'NS'): React.CSSProperties {
  if (band === 'HS') {
    return { background: 'rgba(248,81,73,0.20)', color: '#ff8a82', borderColor: 'rgba(248,81,73,0.40)' };
  }
  if (band === 'LS') {
    return { background: 'rgba(210,153,34,0.18)', color: '#d4a64a', borderColor: 'rgba(210,153,34,0.35)' };
  }
  return { background: 'rgba(63,185,80,0.15)', color: '#56d364', borderColor: 'rgba(63,185,80,0.35)' };
}

function safeColor(au: number) {
  if (au >= 14.3) return 'var(--color-good)';
  if (au >= 7) return 'var(--color-warn)';
  return 'var(--color-bad)';
}

const TH =
  'text-left bg-[var(--color-surface-2)] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3';
const TD = 'border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle';

export default function RouteTable({
  steps,
  zkill,
  alternatives,
  mode = 'safe',
  onSwap,
}: Props) {
  const [selectedStep, setSelectedStep] = useState<RouteStep | null>(null);
  const [expandedHop, setExpandedHop] = useState<number | null>(null);

  const showMoons = mode === 'pos';
  const totalCols = showMoons ? 11 : 10;

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr>
              <th className={`${TH} w-[42px]`}>#</th>
              <th className={TH}>System</th>
              <th className={`${TH} w-[72px]`}>Sec</th>
              <th className={`${TH} text-right w-[60px]`}>LY</th>
              <th className={`${TH} text-right w-[68px]`}>Wait</th>
              <th className={`${TH} text-right w-[80px]`}>Fatigue</th>
              <th className={`${TH} text-right w-[64px]`}>Kills/h</th>
              <th className={`${TH} text-right w-[200px]`}>Hour-of-day (UTC)</th>
              {showMoons && <th className={`${TH} text-right w-[60px]`}>Moons</th>}
              <th className={`${TH} w-[110px]`}>Threat</th>
              <th className={`${TH} text-right w-[80px]`}>Safe AU</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((step, i) => {
              let threat: 'high' | 'mid' | 'none' = 'none';
              let rowBg = '';
              if (step.kills_per_hour > 10) {
                threat = 'high';
                rowBg = 'bg-[rgba(248,81,73,0.10)]';
              } else if (step.kills_per_hour > 3) {
                threat = 'mid';
                rowBg = 'bg-[rgba(210,153,34,0.10)]';
              }

              const z = zkill?.[step.system_id];
              const alts = alternatives?.[String(step.system_id)] || [];
              const isExpanded = expandedHop === i;

              return (
                <React.Fragment key={i}>
                  <tr
                    className={`${rowBg} hover:bg-[var(--color-surface-2)]`}
                    data-row-threat={threat}
                    data-sov-color={getSovColor(step.sov_owner) ?? ''}
                    style={
                      getSovColor(step.sov_owner)
                        ? {
                            boxShadow: `inset 4px 0 0 ${getSovColor(step.sov_owner)}`,
                          }
                        : undefined
                    }
                  >
                    <td className={`${TD} text-right font-mono`}>
                      {i}
                      {i > 0 && alts.length > 0 && (
                        <button
                          onClick={() => setExpandedHop(isExpanded ? null : i)}
                          className="ml-1 text-[10px] text-[var(--color-accent)] hover:underline"
                          title="Show alternative systems"
                        >
                          {isExpanded ? '▾' : '▸'}
                        </button>
                      )}
                    </td>
                    <td className={TD}>
                      <div className="font-semibold text-[var(--color-ink)]">
                        {step.system_name}
                        {step.edge_type === 'gate' && (
                          <span className="pill ml-1.5" style={{ background: 'rgba(88,166,255,0.18)', borderColor: 'rgba(88,166,255,0.40)', color: '#79b8ff' }}>
                            Gate
                          </span>
                        )}
                        {step.gate_count === 1 && (
                          <span className="pill ml-1.5">Dead End</span>
                        )}
                      </div>
                      {step.sov_owner && (
                        <div className="text-[11px] text-[var(--color-muted)]">
                          {step.sov_owner}
                        </div>
                      )}
                    </td>
                    <td className={TD}>
                      <span
                        className="font-semibold mr-1"
                        style={{ color: secColor(step.security) }}
                      >
                        {step.security.toFixed(1)}
                      </span>
                      <span
                        className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold border align-middle"
                        style={secBandStyle(secBand(step.security))}
                        data-testid="sec-band-pill"
                        data-sec-band={secBand(step.security)}
                      >
                        {secBand(step.security)}
                      </span>
                    </td>
                    <td className={`${TD} text-right tabular-nums`}>
                      {step.distance_ly > 0 ? step.distance_ly.toFixed(2) : '—'}
                    </td>
                    <td
                      className={`${TD} text-right tabular-nums`}
                      title={(() => {
                        const cd = step.wait_cooldown_minutes ?? 0;
                        const dc = step.wait_decay_minutes ?? 0;
                        if (cd <= 0 && dc <= 0) return '';
                        return `${formatTime(cd)} red timer + ${formatTime(dc)} fatigue wait`;
                      })()}
                    >
                      {step.wait_minutes > 0 ? formatTime(step.wait_minutes) : '—'}
                      {(() => {
                        const cd = step.wait_cooldown_minutes ?? 0;
                        const dc = step.wait_decay_minutes ?? 0;
                        const total = cd + dc;
                        if (total <= 0) return null;
                        const cdPct = (cd / total) * 100;
                        const dcPct = (dc / total) * 100;
                        return (
                          <div
                            className="mt-0.5 flex h-[3px] w-full overflow-hidden rounded-sm"
                            data-testid="wait-bar"
                          >
                            <span
                              data-testid="wait-bar-cooldown"
                              style={{
                                width: `${cdPct}%`,
                                background: 'var(--color-bad)',
                              }}
                            />
                            <span
                              data-testid="wait-bar-decay"
                              style={{
                                width: `${dcPct}%`,
                                background: 'var(--color-accent)',
                              }}
                            />
                          </div>
                        );
                      })()}
                    </td>
                    <td className={`${TD} text-right tabular-nums`}>
                      {formatTime(step.fatigue_after_minutes)}
                    </td>
                    <td
                      className={`${TD} text-right tabular-nums ${
                        step.kills_per_hour > 10
                          ? 'text-[var(--color-bad)] font-semibold'
                          : step.kills_per_hour > 3
                            ? 'text-[var(--color-warn)]'
                            : ''
                      }`}
                    >
                      {step.kills_per_hour}
                    </td>
                    <td className={`${TD} text-right`}>
                      <div className="flex justify-end">
                        <Sparkline hourly={step.hourly_jumps ?? []} />
                      </div>
                    </td>
                    {showMoons && (
                      <td className={`${TD} text-right tabular-nums`}>
                        {step.moon_count}
                      </td>
                    )}
                    <td
                      data-testid="threat-cell"
                      className={`${TD} text-[11.5px] ${
                        z ? 'cursor-pointer text-[var(--color-accent)] hover:underline' : 'text-[var(--color-muted)]'
                      }`}
                      onClick={() => z && setSelectedStep(step)}
                    >
                      {z ? (
                        <>
                          {z.active_characters ? (
                            <span className="block">{z.active_characters} PVPers</span>
                          ) : null}
                          {z.gang_ratio && z.gang_ratio !== '0%' ? (
                            <span className="block text-[var(--color-muted)]">
                              Gang: {z.gang_ratio}%
                            </span>
                          ) : null}
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td
                      className={`${TD} text-right`}
                      title={[
                        step.safe_spot_warp ? `warp ${step.safe_spot_warp}` : '',
                        step.safe_spot_nearest ? `near ${step.safe_spot_nearest}` : '',
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    >
                      <span
                        className="font-semibold tabular-nums"
                        style={{ color: safeColor(step.safe_spot_au) }}
                      >
                        {step.safe_spot_au.toFixed(1)}
                      </span>
                    </td>
                  </tr>
                  {isExpanded && alts.length > 0 && (
                    <tr>
                      <td colSpan={totalCols} className="p-0">
                        <div className="bg-[var(--color-surface-2)] border-b border-[var(--color-line-soft)] px-4 py-3 text-[11.5px]">
                          <div className="text-[var(--color-muted)] mb-2 font-semibold uppercase tracking-wider text-[11px]">
                            Alternatives reachable from {steps[i - 1]?.system_name}
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                            {alts.map((alt) => (
                              <div
                                key={alt.id}
                                className="flex justify-between items-center bg-[var(--color-paper)] border border-[var(--color-line)] rounded px-2.5 py-1.5 cursor-pointer hover:border-[var(--color-accent)]"
                                onClick={() => {
                                  onSwap?.(i, alt.id);
                                  setExpandedHop(null);
                                }}
                              >
                                <div>
                                  <span className="font-semibold">{alt.name}</span>
                                  <span
                                    className="ml-1.5 font-semibold"
                                    style={{ color: secColor(alt.security) }}
                                  >
                                    {alt.security.toFixed(1)}
                                  </span>
                                  {alt.sov_owner && (
                                    <span className="ml-1.5 text-[var(--color-muted)]">
                                      [{alt.sov_owner}]
                                    </span>
                                  )}
                                </div>
                                <div className="flex gap-3 text-[var(--color-muted)] tabular-nums">
                                  <span>{alt.distance_ly} LY</span>
                                  <span>{alt.moon_count} moons</span>
                                  <span
                                    className="font-semibold"
                                    style={{ color: safeColor(alt.safe_spot_au) }}
                                  >
                                    {alt.safe_spot_au.toFixed(1)} AU
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedStep && zkill?.[selectedStep.system_id] && (
        <ThreatModal
          systemName={selectedStep.system_name}
          systemId={selectedStep.system_id}
          sovOwner={selectedStep.sov_owner}
          stats={zkill[selectedStep.system_id]}
          onClose={() => setSelectedStep(null)}
        />
      )}
    </>
  );
}
