export function formatTime(minutes: number): string {
  if (minutes < 1) return `${Math.round(minutes * 60)}s`;
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return `${h}h ${m}m`;
}

export function secColor(sec: number): string {
  if (sec >= 0.45) return '#2d7a4a';
  if (sec > 0) return '#b07a14';
  return '#b1382f';
}
