/**
 * Alliance / NPC-faction color map. Used by both the map canvas and the
 * route table's per-row left border, so colors stay consistent.
 *
 * Names match the SDE's `sov_alliance_name` / `sov_faction_name` exactly.
 * Falling back to a deterministic hue from the alliance name's hash so
 * unknown alliances still get a stable color across renders.
 */

const KNOWN_SOV_COLORS: Record<string, string> = {
  'Goonswarm Federation': '#ff7733',
  'Pandemic Horde': '#3ec25b',
  'Brave Collective': '#a26ad8',
  'Fraternity.': '#d33e3e',
  'The Initiative.': '#5a8a5a',
  'TEST Alliance Please Ignore': '#5fbf8f',
  'Wings Freedom.': '#d97aa1',
  'Sigma Grindset': '#c4894e',
  'OnlyFleets.': '#7090ff',
  'Reeloaded.': '#dd5577',
  'Dracarys.': '#e0594a',
  'Vanguard.': '#7a9adf',
  'Kinetic Diplomacy': '#a4b85f',
  'Invidia Gloriae Comes': '#cf6f3c',
  'Burning Contingent Holdings': '#b85050',
  'Blood Raider Covenant': '#9a2030',
  'Amarr Empire': '#d4a45a',
  'Caldari State': '#5570a0',
  'Gallente Federation': '#3aa088',
  'Minmatar Republic': '#a25040',
  'Khanid Kingdom': '#b87a3a',
  'Ammatar Mandate': '#a5704a',
  'CONCORD Assembly': '#6f7a90',
  "Sansha's Nation": '#5a4060',
  'Guristas Pirates': '#8a8a40',
  'Serpentis': '#3a8a6a',
  'Angel Cartel': '#9a8030',
  "Mordu's Legion Command": '#5a5fb0',
  'The Society of Conscious Thought': '#7a8a9a',
};

/** Return a stable color for an alliance / faction name, or null when blank. */
export function getSovColor(sov: string): string | null {
  if (!sov) return null;
  const known = KNOWN_SOV_COLORS[sov];
  if (known) return known;
  // Deterministic hash → HSL hue so unknown alliances stay color-stable.
  let h = 0;
  for (let i = 0; i < sov.length; i++) {
    h = (Math.imul(h, 31) + sov.charCodeAt(i)) | 0;
  }
  const hue = Math.abs(h) % 360;
  return `hsl(${hue}, 60%, 58%)`;
}

export { KNOWN_SOV_COLORS };
