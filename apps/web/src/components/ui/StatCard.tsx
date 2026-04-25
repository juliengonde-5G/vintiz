import React from 'react';

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  delta?: number;           // percent change vs prev period
  deltaLabel?: string;      // e.g. "vs 7 derniers jours"
  icon?: React.ReactNode;
  accent?: 'teal' | 'pink' | 'warm' | 'neutral';
  hint?: string;
  className?: string;
}

const accentBg: Record<NonNullable<StatCardProps['accent']>, string> = {
  teal: 'bg-teal-50 text-teal',
  pink: 'bg-pink-50 text-pink-700',
  warm: 'bg-cream text-black',
  neutral: 'bg-gray-50 text-gray-600',
};

export default function StatCard({
  label,
  value,
  delta,
  deltaLabel,
  icon,
  accent = 'teal',
  hint,
  className = '',
}: StatCardProps) {
  const positive = typeof delta === 'number' && delta >= 0;
  return (
    <div className={`rounded-2xl bg-white p-5 shadow-card hover:shadow-soft transition-shadow ${className}`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <p className="text-xs font-medium tracking-wide uppercase text-gray-500">{label}</p>
        {icon && (
          <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${accentBg[accent]}`}>
            {icon}
          </div>
        )}
      </div>
      <p className="text-2xl md:text-3xl font-semibold font-display text-black leading-tight">
        {value}
      </p>
      <div className="flex items-center gap-2 mt-2">
        {typeof delta === 'number' && (
          <span
            className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
              positive ? 'bg-teal-50 text-teal' : 'bg-pink-50 text-pink-700'
            }`}
          >
            <span>{positive ? '▲' : '▼'}</span>
            {Math.abs(delta).toFixed(1)}%
          </span>
        )}
        {deltaLabel && <span className="text-xs text-gray-500">{deltaLabel}</span>}
      </div>
      {hint && <p className="text-xs text-gray-500 mt-2">{hint}</p>}
    </div>
  );
}
