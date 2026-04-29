import React from 'react';

type BadgeVariant =
  | 'default'
  | 'stock'
  | 'display'
  | 'sold'
  | 'returned'
  | 'loyalty'
  | 'tag'
  | 'zone';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-vz-bg-alt text-vz-ink-soft',
  stock: 'bg-vz-bg-alt text-vz-ink-soft',
  display: 'bg-vz-teal-soft text-vz-teal-deep',
  sold: 'bg-green-100 text-green-700',
  returned: 'bg-red-100 text-red-700',
  loyalty: 'bg-vz-accent-soft text-vz-accent',
  tag: 'bg-vz-teal-soft text-vz-teal-deep',
  zone: 'bg-transparent border border-vz-line text-vz-ink-soft',
};

export default function Badge({
  variant = 'default',
  children,
  className = '',
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
