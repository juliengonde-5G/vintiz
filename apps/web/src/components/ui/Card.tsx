import React from 'react';

type Variant = 'default' | 'elevated' | 'bordered' | 'teal' | 'accent';

interface CardProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  variant?: Variant;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  onClick?: () => void;
  as?: 'div' | 'button' | 'a';
  href?: string;
}

const variantClasses: Record<Variant, string> = {
  default: 'bg-vz-surface border border-vz-line',
  elevated: 'bg-vz-surface border border-vz-line shadow-vz-soft',
  bordered: 'bg-vz-surface border border-vz-line',
  teal: 'bg-vz-teal text-white',
  accent: 'bg-vz-accent-soft border border-dashed border-vz-accent',
};

export default function Card({
  title,
  subtitle,
  children,
  className = '',
  variant = 'default',
  action,
  icon,
  onClick,
  as,
  href,
}: CardProps) {
  const base = `rounded-vz-lg p-6 transition-all duration-200 ${variantClasses[variant]} ${className}`;
  const clickable = onClick || href ? 'cursor-pointer active:scale-[0.99]' : '';

  const header = (title || subtitle || action || icon) && (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div className="flex items-start gap-3 min-w-0">
        {icon && (
          <div className={`flex-shrink-0 h-10 w-10 rounded-vz flex items-center justify-center ${
            variant === 'teal' ? 'bg-white/15 text-white' : 'bg-vz-teal-soft text-vz-teal-deep'
          }`}>
            {icon}
          </div>
        )}
        <div className="min-w-0">
          {title && (
            <h3 className={`text-base font-medium leading-tight font-display ${
              variant === 'teal' ? 'text-white' : 'text-vz-ink'
            }`}>{title}</h3>
          )}
          {subtitle && (
            <p className={`text-sm mt-0.5 ${
              variant === 'teal' ? 'text-white/80' : 'text-vz-ink-mute'
            }`}>{subtitle}</p>
          )}
        </div>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );

  const inner = (
    <>
      {header}
      {children}
    </>
  );

  if (as === 'a' && href) {
    return (
      <a href={href} className={`${base} ${clickable} block`}>
        {inner}
      </a>
    );
  }
  if (as === 'button' || onClick) {
    return (
      <button type="button" onClick={onClick} className={`${base} ${clickable} w-full text-left`}>
        {inner}
      </button>
    );
  }
  return <div className={base}>{inner}</div>;
}
