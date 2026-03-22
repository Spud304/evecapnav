import React, { useState } from 'react';
import type { RouteStep, ZkillSystemStats, AlternativeSystem } from '../types';
import { formatTime, secColor } from '../utils/format';
import ThreatModal from './ThreatModal';

interface Props {
  steps: RouteStep[];
  zkill?: Record<number, ZkillSystemStats>;
  alternatives?: Record<string, AlternativeSystem[]>;
  onSwap?: (hopIndex: number, altSystemId: number) => void;
}

export default function RouteTable({ steps, zkill, alternatives, onSwap }: Props) {
  const [selectedStep, setSelectedStep] = useState<RouteStep | null>(null);
  const [expandedHop, setExpandedHop] = useState<number | null>(null);

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-2 border-[#0f3460] text-left text-gray-400">
              <th className="p-2">#</th>
              <th className="p-2">System</th>
              <th className="p-2">Security</th>
              <th className="p-2">Distance (LY)</th>
              <th className="p-2">Wait</th>
              <th className="p-2">Fatigue After</th>
              <th className="p-2">Kills/hr</th>
              <th className="p-2">Jumps/hr</th>
              <th className="p-2">Moons</th>
              <th className="p-2">Threat Intel</th>
              <th className="p-2">Safe Spot</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((step, i) => {
              let rowClass = '';
              if (step.kills_per_hour > 10) rowClass = 'bg-red-900/30';
              else if (step.kills_per_hour > 3) rowClass = 'bg-yellow-900/20';

              const safeColor =
                step.safe_spot_au >= 14.3
                  ? 'text-green-400'
                  : step.safe_spot_au >= 7
                    ? 'text-yellow-400'
                    : 'text-red-400';

              const z = zkill?.[step.system_id];

              const alts = alternatives?.[String(step.system_id)] || [];
              const isExpanded = expandedHop === i;

              return (
                <React.Fragment key={i}>
                <tr className={`border-b border-gray-700/50 ${rowClass}`}>
                  <td className="p-2">
                    {i}
                    {i > 0 && alts.length > 0 && (
                      <button
                        onClick={() => setExpandedHop(isExpanded ? null : i)}
                        className="ml-1 text-xs text-blue-400 hover:text-blue-300"
                        title="Show alternative systems"
                      >
                        {isExpanded ? '▼' : '▶'}
                      </button>
                    )}
                  </td>
                  <td className="p-2">
                    <span className="font-medium">{step.system_name}</span>
                    {step.sov_owner && (
                      <span className="block text-xs text-gray-500">{step.sov_owner}</span>
                    )}
                  </td>
                  <td className="p-2" style={{ color: secColor(step.security) }}>
                    {step.security.toFixed(1)}
                  </td>
                  <td className="p-2">
                    {step.distance_ly > 0 ? step.distance_ly.toFixed(2) : '—'}
                  </td>
                  <td className="p-2">
                    {step.wait_minutes > 0 ? formatTime(step.wait_minutes) : '—'}
                  </td>
                  <td className="p-2">{formatTime(step.fatigue_after_minutes)}</td>
                  <td className="p-2">{step.kills_per_hour}</td>
                  <td className="p-2">{step.jumps_per_hour}</td>
                  <td className="p-2">{step.moon_count}</td>
                  <td
                    className={`p-2 text-xs ${z ? 'cursor-pointer hover:text-blue-400' : ''}`}
                    onClick={() => z && setSelectedStep(step)}
                  >
                    {z ? (
                      <>
                        {z.active_characters ? (
                          <span className="block underline">{z.active_characters} PVPers</span>
                        ) : null}
                        {z.gang_ratio && z.gang_ratio !== '0%' ? (
                          <span className="block text-gray-500">Group Kills: {z.gang_ratio}%</span>
                        ) : null}
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="p-2">
                    <span className={`font-bold ${safeColor}`}>
                      {step.safe_spot_au.toFixed(1)} AU
                    </span>
                    {step.safe_spot_warp && (
                      <span className="block text-xs text-gray-500">
                        Warp: {step.safe_spot_warp}
                      </span>
                    )}
                    {step.safe_spot_nearest && (
                      <span className="block text-xs text-gray-500">
                        Nearest: {step.safe_spot_nearest}
                      </span>
                    )}
                  </td>
                </tr>
                {isExpanded && alts.length > 0 && (
                  <tr>
                    <td colSpan={11} className="p-0">
                      <div className="bg-gray-900/50 px-4 py-2 text-xs">
                        <div className="text-gray-400 mb-1 font-medium">
                          Alternative systems reachable from {steps[i - 1]?.system_name}:
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
                          {alts.map((alt) => (
                            <div
                              key={alt.id}
                              className="flex justify-between items-center bg-gray-800/50 rounded px-2 py-1 cursor-pointer hover:bg-gray-700/50"
                              onClick={() => {
                                onSwap?.(i, alt.id);
                                setExpandedHop(null);
                              }}
                            >
                              <div>
                                <span className="font-medium">{alt.name}</span>
                                <span className="ml-1" style={{ color: secColor(alt.security) }}>
                                  ({alt.security.toFixed(1)})
                                </span>
                                {alt.sov_owner && (
                                  <span className="ml-1 text-gray-500">[{alt.sov_owner}]</span>
                                )}
                              </div>
                              <div className="flex gap-3 text-gray-400">
                                <span>{alt.distance_ly} LY</span>
                                <span>{alt.moon_count} moons</span>
                                <span
                                  className={
                                    alt.safe_spot_au >= 14.3
                                      ? 'text-green-400'
                                      : alt.safe_spot_au >= 7
                                        ? 'text-yellow-400'
                                        : 'text-red-400'
                                  }
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
