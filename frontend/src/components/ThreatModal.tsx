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
        className="bg-[#16213e] border border-[#0f3460] rounded-lg p-6 w-full max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-semibold">{systemName}</h3>
            {sovOwner && (
              <span className="text-sm text-gray-400">{sovOwner}</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
          <div className="bg-gray-800/50 rounded p-3">
            <div className="text-gray-400">Active PVPers</div>
            <div className="text-xl font-bold">{stats.active_characters || 0}</div>
          </div>
          <div className="bg-gray-800/50 rounded p-3">
            <div className="text-gray-400">Active Corps</div>
            <div className="text-xl font-bold">{stats.active_corps || 0}</div>
          </div>
          <div className="bg-gray-800/50 rounded p-3">
            <div className="text-gray-400">Ships Destroyed</div>
            <div className="text-xl font-bold">
              {(stats.ships_destroyed || 0).toLocaleString()}
            </div>
          </div>
          <div className="bg-gray-800/50 rounded p-3">
            <div className="text-gray-400">Group Kills</div>
            <div className="text-xl font-bold">{stats.gang_ratio || '0'}%</div>
          </div>
        </div>

        {hourly.length === 24 && (
          <div className="mb-4">
            <div className="text-sm text-gray-400 mb-2">
              Hourly Activity (UTC)
            </div>
            <div className="flex items-end gap-px h-20">
              {hourly.map((count, hour) => (
                <div
                  key={hour}
                  className="flex-1 group relative"
                  title={`${String(hour).padStart(2, '0')}:00 — ${count} kills`}
                >
                  <div
                    className="w-full rounded-t"
                    style={{
                      height: `${(count / maxActivity) * 100}%`,
                      minHeight: count > 0 ? '2px' : '0',
                      backgroundColor:
                        count / maxActivity > 0.7
                          ? '#dc3545'
                          : count / maxActivity > 0.3
                            ? '#f39c12'
                            : '#2ecc71',
                    }}
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
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
          className="block text-center text-sm text-blue-400 hover:text-blue-300"
        >
          View on zKillboard &rarr;
        </a>
      </div>
    </div>
  );
}
