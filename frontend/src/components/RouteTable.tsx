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
  'text-left bg-[var(--color-surface-2)] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 whitespace-nowrap';
const TD = 'border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle';

/** Small ⓘ tooltip icon next to a column header.
 *
 * Uses the native `title` attribute on a dedicated <span> so the hover
 * trigger is just the icon rather than the whole th (which would fire
 * the tooltip whenever the user hovered anywhere in the column header).
 */
function HeaderInfo({ text }: { text: string }) {
  return (
    <span
      className="ml-1 cursor-help align-middle normal-case tracking-normal text-[10px] opacity-70 hover:opacity-100"
      title={text}
      data-testid="header-info"
      aria-label={text}
    >
      ⓘ
    </span>
  );
}

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
              <th className={TH}>
                System
                <HeaderInfo text="System name. Color-band pill on the right of the row shows alliance / faction sov holder; the colored stripe at the row's left edge encodes the same alliance." />
              </th>
              <th className={`${TH} w-[72px]`}>
                Sec
                <HeaderInfo text="True security status (raw float — not the rounded display value). HS = hi-sec, LS = low-sec, NS = null-sec. Capital ships can't gate-jump into HS." />
              </th>
              <th className={`${TH} text-right w-[60px]`}>
                LY
                <HeaderInfo text="Light-years jumped to reach this system from the previous one. Empty for the origin and gate hops (gate distance is informational only)." />
              </th>
              <th className={`${TH} text-right w-[68px]`}>
                Wait
                <HeaderInfo text="Time you wait at this system before the next hop. The two-tone bar splits the wait into red-timer cooldown (mandatory between JDs) and blue-timer fatigue decay (optional, only worth taking if it shortens the next jump's cooldown)." />
              </th>
              <th className={`${TH} text-right w-[80px]`}>
                Fatigue
                <HeaderInfo text="Jump fatigue accumulated AFTER this hop, including any wait-decay you took. Hard caps at 300 minutes. Decays 1 minute per real minute." />
              </th>
              <th className={`${TH} text-right w-[64px]`}>
                Kills/h
                <HeaderInfo text="Ship kills in this system over the most recent hour, from ESI. Updates hourly. Rows tint amber at 4+ and red at 11+ to flag active hunting." />
              </th>
              <th className={`${TH} text-right w-[220px]`}>
                Hour-of-day · weekly avg (UTC)
                <HeaderInfo text="Per-hour jump traffic profile, AVERAGED OVER THE PAST 7 DAYS. Each bar = one UTC hour, height = mean ship_jumps that hour. Peak / Quiet labels under the bars show the busiest and quietest hour; the amber outlined bar is the current UTC hour." />
              </th>
              {showMoons && (
                <th className={`${TH} text-right w-[60px]`}>
                  Moons
                  <HeaderInfo text="Moon count in this system. Only shown in POS-Hopping mode — useful for picking moon-rich systems for safe spots and POS bookmarks." />
                </th>
              )}
              <th className={`${TH} w-[110px]`}>
                Threat
                <HeaderInfo text="Recent PVP activity from zKillboard. Active PVPers is the rolling count of distinct attackers; Gang % is the fraction of recorded kills with 2+ attackers (gang vs solo). Click the cell for the full breakdown including 24-hour activity histogram." />
              </th>
              <th className={`${TH} text-right w-[170px]`}>
                Safe AU
                <HeaderInfo text="Distance in AU between the safest pair of celestials in this system — bigger = better mid-warp safe spot. The 'warp X-Y' line names the two planets to bookmark, and 'near Z' is the nearest probe-able reference." />
              </th>
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
                        if (step.edge_type === 'gate') {
                          return `Gate travel + any pre-jump fatigue decay (gates have no red-timer cooldown)`;
                        }
                        const cd = step.wait_cooldown_minutes ?? 0;
                        const dc = step.wait_decay_minutes ?? 0;
                        if (cd <= 0 && dc <= 0) return '';
                        return `${formatTime(cd)} red timer + ${formatTime(dc)} fatigue wait`;
                      })()}
                    >
                      {step.wait_minutes > 0 ? formatTime(step.wait_minutes) : '—'}
                      {(() => {
                        // Two-tone bar is meaningful only for JD hops, which
                        // are the only edges that produce a red-timer cooldown.
                        // Gate hops mix travel-time + decay waiting and have no
                        // red timer at all — rendering a half-red bar for them
                        // is visually misleading.
                        if (step.edge_type !== 'jump') return null;
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
                              Gang: {z.gang_ratio}
                            </span>
                          ) : null}
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td
                      className={`${TD} text-right max-w-[170px]`}
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
                      {step.safe_spot_warp && (
                        <span
                          className="block text-[10.5px] text-[var(--color-muted)] font-normal truncate"
                          title={`warp ${step.safe_spot_warp}`}
                        >
                          warp {step.safe_spot_warp}
                        </span>
                      )}
                      {step.safe_spot_nearest && (
                        <span
                          className="block text-[10.5px] text-[var(--color-muted)] font-normal truncate"
                          title={`near ${step.safe_spot_nearest}`}
                        >
                          near {step.safe_spot_nearest}
                        </span>
                      )}
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
