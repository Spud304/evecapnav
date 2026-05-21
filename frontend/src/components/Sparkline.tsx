interface Props {
  /** 24-element list of jumps/hour, UTC index 0=00:00. */
  hourly: number[];
  /** Show peak / quiet / now numeric anchors below the bars. */
  annotated?: boolean;
  /** Compact mode — narrower bars, no annotations. */
  compact?: boolean;
}

function isValid(hourly: number[] | undefined): hourly is number[] {
  return Array.isArray(hourly) && hourly.length === 24;
}

export default function Sparkline({ hourly, annotated = true, compact = false }: Props) {
  if (!isValid(hourly) || hourly.every((v) => v === 0)) {
    return (
      <span
        className="text-[var(--color-muted)] text-[10.5px]"
        data-testid="sparkline-empty"
      >
        no data
      </span>
    );
  }

  const max = Math.max(...hourly, 1);
  const min = Math.min(...hourly);
  const peakIdx = hourly.indexOf(max);
  const quietIdx = hourly.indexOf(min);
  const nowHour = new Date().getUTCHours();
  const barHeightPx = compact ? 20 : 26;
  const barWidthPx = compact ? 3 : 5;

  return (
    <div className="flex flex-col items-end gap-1" data-testid="sparkline">
      <div
        className="spark"
        style={{ height: barHeightPx + 4 }}
      >
        {hourly.map((v, h) => {
          const classes = ['bar'];
          if (h === peakIdx) classes.push('peak');
          if (h === quietIdx) classes.push('quiet');
          if (h === nowHour) classes.push('now');
          return (
            <div
              key={h}
              className={classes.join(' ')}
              style={{
                width: barWidthPx,
                height: Math.max(2, Math.round((v / max) * barHeightPx)),
              }}
              title={`${String(h).padStart(2, '0')}:00 UTC — ${v.toFixed(1)} jumps/hr`}
            />
          );
        })}
      </div>
      {annotated && !compact && (
        <div className="spark-ann">
          <span className="peak">Peak {Math.round(max)} @ {String(peakIdx).padStart(2, '0')}h</span>
          <span className="quiet">Quiet {Math.round(min)} @ {String(quietIdx).padStart(2, '0')}h</span>
          <span className="now">Now {Math.round(hourly[nowHour])}/hr</span>
        </div>
      )}
    </div>
  );
}
