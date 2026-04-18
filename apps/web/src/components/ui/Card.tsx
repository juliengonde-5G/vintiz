import React from 'react';

type Variant = 'default' | 'elevated' | 'bordered' | 'gradient' | 'teal' | 'pink';

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
  default: 'bg-white shadow-card hover:shadow-soft',
  elevated: 'bg-white shadow-soft hover:shadow-depth',
  bordered: 'bg-white border border-teal-50 shadow-sm hover:border-teal-200',
  gradient: 'bg-gradient-card border border-teal-50 shadow-soft',
  teal: 'bg-gradient-teal text-white shadow-depth',
  pink: 'bg-pink-50 border border-pink-100 shadow-sm',
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
  const base = `rounded-2xl p-6 transition-all duration-200 ${variantClasses[variant]} ${className}`;
  const clickable = onClick || href ? 'cursor-pointer active:scale-[0.99]' : '';

  const header = (title || subtitle || action || icon) && (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div className="flex items-start gap-3 min-w-0">
        {icon && (
          <div className={`flex-shrink-0 h-10 w-10 rounded-xl flex items-center justify-center ${
            variant === 'teal' ? 'bg-white/15 text-white' : 'bg-teal-50 text-teal'
          }`}>
            {icon}
          </div>
        )}
        <div className="min-w-0">
          {title && (
            <h3 className={`text-base font-semibold leading-tight font-display ${
              variant === 'teal' ? 'text-white' : 'text-black'
            }`}>{title}</h3>
          )}
          {subtitle && (
            <p className={`text-sm mt-0.5 ${
              variant === 'teal' ? 'text-white/80' : 'text-gray-500'
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
