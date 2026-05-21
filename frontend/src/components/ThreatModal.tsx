import type { ZkillSystemStats } from '../types';

interface Props {
  systemName: string;
  systemId: number;
  sovOwner: string;
  stats: ZkillSystemStats;
  onClose: () => void;
}

export default function ThreatModal({
  systemName,
  systemId,
  sovOwner,
  stats,
  onClose,
}: Props) {
  const hourly = stats.hourly_activity || [];
  const maxActivity = Math.max(...hourly, 1);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="card-head justify-between">
          <div className="flex items-baseline gap-2">
            <h2 className="!text-[14px] !tracking-normal !normal-case !text-[var(--color-ink)]">
              {systemName}
            </h2>
            {sovOwner && (
              <span className="text-[12px] text-[var(--color-muted)]">{sovOwner}</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-[var(--color-ink)] text-xl leading-none cursor-pointer"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="card-body">
          <div className="grid grid-cols-2 gap-3 mb-4 text-[12px]">
            <div className="border border-[var(--color-line)] rounded-md p-3 bg-[var(--color-surface-2)]">
              <div className="text-[var(--color-muted)] text-[11px] uppercase tracking-wider">
                Active PVPers
              </div>
              <div className="text-xl font-semibold">{stats.active_characters || 0}</div>
            </div>
            <div className="border border-[var(--color-line)] rounded-md p-3 bg-[var(--color-surface-2)]">
              <div className="text-[var(--color-muted)] text-[11px] uppercase tracking-wider">
                Active Corps
              </div>
              <div className="text-xl font-semibold">{stats.active_corps || 0}</div>
            </div>
            <div className="border border-[var(--color-line)] rounded-md p-3 bg-[var(--color-surface-2)]">
              <div className="text-[var(--color-muted)] text-[11px] uppercase tracking-wider">
                Ships Destroyed
              </div>
              <div className="text-xl font-semibold">
                {(stats.ships_destroyed || 0).toLocaleString()}
              </div>
            </div>
            <div className="border border-[var(--color-line)] rounded-md p-3 bg-[var(--color-surface-2)]">
              <div className="text-[var(--color-muted)] text-[11px] uppercase tracking-wider">
                Group Kills
              </div>
              <div className="text-xl font-semibold">{stats.gang_ratio || '0'}%</div>
            </div>
          </div>

          {hourly.length === 24 && (
            <div className="mb-4">
              <div className="text-[11px] uppercase tracking-wider text-[var(--color-muted)] mb-2">
                Hourly Activity (UTC)
              </div>
              <div className="flex items-end gap-px h-20 border-b border-[var(--color-line)]">
                {hourly.map((count, hour) => (
                  <div
                    key={hour}
                    className="flex-1"
                    title={`${String(hour).padStart(2, '0')}:00 — ${count} kills`}
                  >
                    <div
                      className="w-full rounded-t"
                      style={{
                        height: `${(count / maxActivity) * 100}%`,
                        minHeight: count > 0 ? '2px' : '0',
                        backgroundColor:
                          count / maxActivity > 0.7
                            ? 'var(--color-bad)'
                            : count / maxActivity > 0.3
                              ? 'var(--color-warn)'
                              : 'var(--color-good)',
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-[10.5px] text-[var(--color-muted)] mt-1">
                <span>00:00</span>
                <span>06:00</span>
                <span>12:00</span>
                <span>18:00</span>
                <span>23:00</span>
              </div>
            </div>
          )}

          <a
            href={`https://zkillboard.com/system/${systemId}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-center text-[12px]"
          >
            View on zKillboard →
          </a>
        </div>
      </div>
    </div>
  );
}
