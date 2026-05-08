'use client';

import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export default function Input({
  label,
  error,
  icon,
  className = '',
  id,
  ...props
}: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-[11px] uppercase tracking-[0.12em] font-medium text-vz-ink-mute mb-1.5"
        >
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-vz-ink-mute">
            {icon}
          </div>
        )}
        <input
          id={inputId}
          className={`w-full min-h-[48px] px-4 py-2.5 rounded-vz border bg-vz-surface text-vz-ink placeholder-vz-ink-mute transition-colors focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal ${
            icon ? 'pl-10' : ''
          } ${
            error
              ? 'border-red-500 focus:ring-red-500 focus:border-red-500'
              : 'border-vz-line'
          } ${className}`}
          {...props}
        />
      </div>
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}
