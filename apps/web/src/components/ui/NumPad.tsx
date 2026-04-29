'use client';

import React, { useState, useEffect } from 'react';

interface NumPadProps {
  value: number;
  onChange: (value: number) => void;
  presets?: number[];
}

export default function NumPad({ value, onChange, presets }: NumPadProps) {
  const [raw, setRaw] = useState(value > 0 ? value.toFixed(2) : '');

  useEffect(() => {
    const parsed = parseFloat(raw) || 0;
    const stable = !raw.endsWith('.') && !raw.endsWith('.0') && !raw.endsWith('.00');
    if (stable && Math.abs(parsed - value) > 0.001) {
      setRaw(value > 0 ? value.toFixed(2) : '');
    }
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  const commit = (r: string) => {
    setRaw(r);
    onChange(parseFloat(r) || 0);
  };

  const press = (k: string) => {
    if (k === '⌫') { commit(raw.length > 1 ? raw.slice(0, -1) : ''); return; }
    if (k === '.') { if (!raw.includes('.')) commit((raw || '0') + '.'); return; }
    if (raw.includes('.') && (raw.split('.')[1]?.length ?? 0) >= 2) return;
    commit((!raw || raw === '0') ? k : raw + k);
  };

  return (
    <div className="space-y-2">
      {/* Value display */}
      <div className="text-right px-4 py-3 bg-gray-50 rounded-xl">
        <span className="text-3xl font-bold text-black tabular-nums">
          {raw || '0'} <span className="text-xl font-normal text-gray-400">€</span>
        </span>
      </div>

      {/* Preset buttons */}
      {presets && presets.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {presets.map((p, i) => (
            <button
              key={i}
              type="button"
              onClick={() => { const v = p.toFixed(2); setRaw(v); onChange(p); }}
              className="flex-1 min-w-[56px] py-2.5 bg-vz-teal-soft hover:bg-vz-teal-soft active:bg-vz-teal-soft text-vz-teal rounded-xl text-sm font-bold transition-colors"
            >
              {Number.isInteger(p) ? `${p} €` : `${p.toFixed(2)} €`}
            </button>
          ))}
        </div>
      )}

      {/* Digit grid */}
      <div className="grid grid-cols-3 gap-2">
        {['7', '8', '9', '4', '5', '6', '1', '2', '3', '.', '0', '⌫'].map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => press(k)}
            className={`py-4 rounded-xl text-2xl font-bold select-none transition-all active:scale-95 ${
              k === '⌫'
                ? 'bg-red-50 text-red-500 hover:bg-red-100 active:bg-red-200'
                : 'bg-white border border-gray-200 text-black hover:bg-vz-accent-soft hover:border-vz-accent-soft shadow-sm'
            }`}
          >
            {k}
          </button>
        ))}
      </div>
    </div>
  );
}
