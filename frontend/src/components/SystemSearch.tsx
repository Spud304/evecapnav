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
    <div ref={wrapRef} className="relative">
      <label className="block text-sm mb-1 text-gray-300">{label}</label>
      <input
        type="text"
        value={query}
        onChange={(e) => handleInput(e.target.value)}
        placeholder="Type system name..."
        autoComplete="off"
        className="w-full px-3 py-2 rounded bg-gray-800 border border-gray-600 text-gray-200 focus:outline-none focus:border-blue-500"
      />
      {open && (
        <div className="absolute z-50 w-full bg-[#16213e] border border-[#0f3460] border-t-0 max-h-48 overflow-y-auto">
          {results.map((s) => (
            <div
              key={s.id}
              onClick={() => handleSelect(s)}
              className="px-3 py-1.5 cursor-pointer hover:bg-[#0f3460] text-gray-200"
            >
              {s.name}{' '}
              <span style={{ color: secColor(s.security) }}>
                ({s.security.toFixed(1)})
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
