import { useState, useEffect, useRef, useMemo } from 'react';
import { getCapShips } from '../api';
import type { CapShip } from '../types';

interface Props {
  /** Currently selected ship type name (e.g. "Nyx"). Empty string until picked. */
  value: string;
  /** JDC skill level — feeds the effective-range badge calculation. */
  jdcLevel: number;
  /** Called with the picked ship — caller stores both type_name and class_label. */
  onSelect: (ship: CapShip) => void;
}

export default function ShipPicker({ value, jdcLevel, onSelect }: Props) {
  const [query, setQuery] = useState(value);
  const [ships, setShips] = useState<CapShip[]>([]);
  const [selected, setSelected] = useState<CapShip | null>(null);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setQuery(value); }, [value]);

  useEffect(() => {
    getCapShips().then((ships) => {
      setShips(ships);
      // Mirror the old dropdown's default-to-first behavior so existing
      // tests + casual users don't see a "Please pick a ship" error.
      if (!value && ships.length > 0) {
        setSelected(ships[0]);
        onSelect(ships[0]);
      } else if (value) {
        const match = ships.find((s) => s.type_name === value);
        if (match) setSelected(match);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  // Match either the ship type name OR the class label (so "carrier" still
  // finds Archon, Thanatos, etc.). Empty query shows everything when focused.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ships;
    return ships.filter(
      (s) =>
        s.type_name.toLowerCase().includes(q) ||
        s.class_label.toLowerCase().includes(q),
    );
  }, [query, ships]);

  function commit(ship: CapShip) {
    setQuery(ship.type_name);
    setSelected(ship);
    setOpen(false);
    onSelect(ship);
  }

  // Effective range = base × (1 + 0.20 × JDC). Mirrors
  // src/stores/ship_store.py::get_effective_range so the badge updates
  // without a backend round-trip whenever JDC changes.
  const effRange = selected
    ? selected.base_range_ly * (1 + 0.2 * jdcLevel)
    : null;

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setOpen(true);
        return;
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(filtered.length - 1, h + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[highlight]) commit(filtered[highlight]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  }

  return (
    <div ref={wrapRef} className="relative flex flex-col">
      <label className="field-label">Ship</label>
      <input
        type="text"
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); setHighlight(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKey}
        placeholder="Archon, Nyx, Naglfar…"
        autoComplete="off"
        className="input"
        data-testid="ship-picker-input"
      />
      {selected && effRange != null && (
        <div
          className="mt-1 text-[10.5px] text-[var(--color-muted)]"
          data-testid="ship-range-badge"
        >
          Range{' '}
          <span className="text-[var(--color-ink)] font-semibold">
            {effRange.toFixed(1)} LY
          </span>{' '}
          · Fuel{' '}
          <span className="text-[var(--color-ink)] font-semibold">
            {selected.fuel_per_ly}/LY
          </span>{' '}
          · Fatigue{' '}
          <span className="text-[var(--color-ink)] font-semibold">
            ×{selected.fatigue_multiplier}
          </span>
        </div>
      )}
      {open && filtered.length > 0 && (
        <div className="absolute z-50 left-0 right-0 top-full mt-px bg-[var(--color-paper)] border border-[var(--color-line)] rounded-b-md shadow-md max-h-64 overflow-y-auto">
          {filtered.map((s, i) => (
            <div
              key={s.type_id}
              onClick={() => commit(s)}
              onMouseEnter={() => setHighlight(i)}
              data-testid="ship-picker-option"
              data-ship-name={s.type_name}
              className={`px-3 py-1.5 cursor-pointer text-[12px] flex items-baseline justify-between ${
                i === highlight ? 'bg-[var(--color-surface-2)]' : ''
              }`}
            >
              <span className="text-[var(--color-ink)]">{s.type_name}</span>
              <span className="text-[var(--color-muted)] text-[11px]">
                {s.class_label} · {s.base_range_ly} LY
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
