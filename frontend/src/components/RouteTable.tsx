import React, { useState } from 'react';
import type { RouteStep, ZkillSystemStats, AlternativeSystem } from '../types';
import { formatTime, secColor } from '../utils/format';
import ThreatModal from './ThreatModal';

interface Props {
  steps: RouteStep[];
  zkill?: Record<number, ZkillSystemStats>;
  alternatives?: Record<string, AlternativeSystem[]>;
  jumpDataWindow?: '1h' | '24h';
  onSwap?: (hopIndex: number, altSystemId: number) => void;
}

function safeColor(au: number) {
  if (au >= 14.3) return 'var(--color-good)';
  if (au >= 7) return 'var(--color-warn)';
  return 'var(--color-bad)';
}

export default function RouteTable({
  steps,
  zkill,
  alternatives,
  jumpDataWindow,
  onSwap,
}: Props) {
  const [selectedStep, setSelectedStep] = useState<RouteStep | null>(null);
  const [expandedHop, setExpandedHop] = useState<number | null>(null);

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr>
              <th className="text-left bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[42px]">
                #
              </th>
              <th className="text-left bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3">
                System
              </th>
              <th className="text-left bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[48px]">
                Sec
              </th>
              <th className="text-right bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[60px]">
                LY
              </th>
              <th className="text-right bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[68px]">
                Wait
              </th>
              <th className="text-right bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[80px]">
                Fatigue
              </th>
              <th className="text-right bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[64px]">
                Kills/h
              </th>
              <th className="text-right bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[72px]">
                Jumps/{jumpDataWindow === '24h' ? '24h' : 'h'}
              </th>
              <th className="text-right bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[60px]">
                Moons
              </th>
              <th className="text-left bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[110px]">
                Threat
              </th>
              <th className="text-right bg-[#fafbfc] border-b border-[var(--color-line)] text-[var(--color-muted)] font-semibold text-[11px] tracking-wider uppercase py-[9px] px-3 w-[80px]">
                Safe AU
              </th>
            </tr>
          </thead>
          <tbody>
            {steps.map((step, i) => {
              let rowBg = '';
              if (step.kills_per_hour > 10) rowBg = 'bg-red-50';
              else if (step.kills_per_hour > 3) rowBg = 'bg-amber-50';

              const z = zkill?.[step.system_id];
              const alts = alternatives?.[String(step.system_id)] || [];
              const isExpanded = expandedHop === i;

              return (
                <React.Fragment key={i}>
                  <tr className={`${rowBg} hover:bg-[#f9fafc]`}>
                    <td className="border-b border-[var(--color-line-soft)] py-[11px] px-3 text-right align-middle font-mono">
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
                    <td className="border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle">
                      <div className="font-semibold text-[var(--color-ink)]">
                        {step.system_name}
                        {step.edge_type === 'gate' && (
                          <span className="pill ml-1.5 bg-[var(--color-accent)] text-white">
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
                    <td
                      className="border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle font-semibold"
                      style={{ color: secColor(step.security) }}
                    >
                      {step.security.toFixed(1)}
                    </td>
                    <td className="border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle text-right tabular-nums">
                      {step.distance_ly > 0 ? step.distance_ly.toFixed(2) : '—'}
                    </td>
                    <td className="border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle text-right tabular-nums">
                      {step.wait_minutes > 0 ? formatTime(step.wait_minutes) : '—'}
                    </td>
                    <td className="border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle text-right tabular-nums">
                      {formatTime(step.fatigue_after_minutes)}
                    </td>
                    <td
                      className={`border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle text-right tabular-nums ${
                        step.kills_per_hour > 10
                          ? 'text-[var(--color-bad)] font-semibold'
                          : step.kills_per_hour > 3
                            ? 'text-[var(--color-warn)]'
                            : ''
                      }`}
                    >
                      {step.kills_per_hour}
                    </td>
                    <td className="border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle text-right tabular-nums">
                      {step.jumps_per_hour}
                    </td>
                    <td className="border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle text-right tabular-nums">
                      {step.moon_count}
                    </td>
                    <td
                      className={`border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle text-[11.5px] ${
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
                    <td className="border-b border-[var(--color-line-soft)] py-[11px] px-3 align-middle text-right">
                      <span
                        className="font-semibold tabular-nums"
                        style={{ color: safeColor(step.safe_spot_au) }}
                      >
                        {step.safe_spot_au.toFixed(1)}
                      </span>
                      {step.safe_spot_warp && (
                        <span className="block text-[10.5px] text-[var(--color-muted)] font-normal">
                          warp {step.safe_spot_warp}
                        </span>
                      )}
                      {step.safe_spot_nearest && (
                        <span className="block text-[10.5px] text-[var(--color-muted)] font-normal">
                          near {step.safe_spot_nearest}
                        </span>
                      )}
                    </td>
                  </tr>
                  {isExpanded && alts.length > 0 && (
                    <tr>
                      {/* colSpan covers the widest case (11 cols at xl+) */}
                      <td colSpan={11} className="p-0">
                        <div className="bg-[#fafbfc] border-b border-[var(--color-line-soft)] px-4 py-3 text-[11.5px]">
                          <div className="text-[var(--color-muted)] mb-2 font-semibold uppercase tracking-wider text-[11px]">
                            Alternatives reachable from {steps[i - 1]?.system_name}
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                            {alts.map((alt) => (
                              <div
                                key={alt.id}
                                className="flex justify-between items-center bg-white border border-[var(--color-line)] rounded px-2.5 py-1.5 cursor-pointer hover:border-[var(--color-accent)]"
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
