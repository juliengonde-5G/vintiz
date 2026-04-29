import React from 'react';

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  eyebrow?: string;
  className?: string;
}

export default function SectionHeader({
  title,
  subtitle,
  icon,
  action,
  eyebrow,
  className = '',
}: SectionHeaderProps) {
  return (
    <div className={`flex items-end justify-between gap-4 mb-5 ${className}`}>
      <div className="flex items-start gap-3 min-w-0">
        {icon && (
          <div className="flex-shrink-0 h-11 w-11 rounded-xl bg-vz-teal-soft text-vz-teal flex items-center justify-center">
            {icon}
          </div>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium mb-1">
              {eyebrow}
            </p>
          )}
          <h2 className="text-xl md:text-2xl font-semibold font-display text-black leading-tight">
            {title}
          </h2>
          {subtitle && (
            <p className="text-sm text-gray-600 mt-1">{subtitle}</p>
          )}
        </div>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}
