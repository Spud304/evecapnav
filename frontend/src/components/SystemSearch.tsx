import { useState, useRef, useEffect } from 'react';
import { searchSystems } from '../api';
import type { SystemSearchResult } from '../types';
import { secColor } from '../utils/format';

interface Props {
  label: string;
  onSelect: (id: number, name: string) => void;
}

export default function SystemSearch({ label, onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SystemSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  function handleInput(value: string) {
    setQuery(value);
    clearTimeout(timerRef.current);
    if (value.trim().length < 2) {
      setOpen(false);
      return;
    }
    timerRef.current = setTimeout(async () => {
      const data = await searchSystems(value.trim());
      setResults(data);
      setOpen(data.length > 0);
    }, 300);
  }

  function handleSelect(s: SystemSearchResult) {
    setQuery(s.name);
    setOpen(false);
    onSelect(s.id, s.name);
  }

  return (
    <div ref={wrapRef} className="relative flex flex-col">
      <label className="field-label">{label}</label>
      <input
        type="text"
        value={query}
        onChange={(e) => handleInput(e.target.value)}
        placeholder="Type system name…"
        autoComplete="off"
        className="input"
      />
      {open && (
        <div className="absolute z-50 left-0 right-0 top-full mt-px bg-white border border-[var(--color-line)] rounded-b-md shadow-md max-h-48 overflow-y-auto">
          {results.map((s) => (
            <div
              key={s.id}
              onClick={() => handleSelect(s)}
              className="px-3 py-1.5 cursor-pointer hover:bg-[#f6f7f9] text-[var(--color-ink)] text-[12px]"
            >
              {s.name}{' '}
              <span
                className="font-semibold"
                style={{ color: secColor(s.security) }}
              >
                ({s.security.toFixed(1)})
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
