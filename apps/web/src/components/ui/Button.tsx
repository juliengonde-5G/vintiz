'use client';

import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-vz-teal text-white hover:bg-vz-teal-deep active:bg-vz-teal-deep',
  secondary: 'bg-vz-surface text-vz-ink border border-vz-ink hover:bg-vz-bg-alt',
  outline: 'bg-transparent border border-vz-line text-vz-ink hover:bg-vz-bg-alt',
  ghost: 'bg-transparent text-vz-ink-soft hover:bg-vz-bg-alt',
  danger: 'bg-red-600 text-white hover:bg-red-700 active:bg-red-800',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm min-h-[36px]',
  md: 'px-4 py-2 text-base min-h-[44px]',
  lg: 'px-6 py-3 text-lg min-h-[48px]',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-vz font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-vz-teal focus:ring-offset-2 focus:ring-offset-vz-bg disabled:opacity-50 disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
